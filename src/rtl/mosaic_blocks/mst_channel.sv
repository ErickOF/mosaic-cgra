`timescale 1ns / 1ps
`default_nettype none

module mst_channel #(
    parameter IS_LOAD = 1,
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
        ((ADDR_WIDTH > 0) === 1'b1) && (((^ADDR_WIDTH == 1'b0) || (^ADDR_WIDTH == 1'b1)) === 1'b1) &&
        ((SHELL_DATA_WIDTH > 0) === 1'b1) && (((^SHELL_DATA_WIDTH == 1'b0) || (^SHELL_DATA_WIDTH == 1'b1)) === 1'b1) &&
        ((MEMORY_DATA_WIDTH > 0) === 1'b1) && (((^MEMORY_DATA_WIDTH == 1'b0) || (^MEMORY_DATA_WIDTH == 1'b1)) === 1'b1) &&
        ((NUM_STREAM_INPUTS > 0) === 1'b1) && (((^NUM_STREAM_INPUTS == 1'b0) || (^NUM_STREAM_INPUTS == 1'b1)) === 1'b1) &&
        ((NUM_STREAM_OUTPUTS > 0) === 1'b1) && (((^NUM_STREAM_OUTPUTS == 1'b0) || (^NUM_STREAM_OUTPUTS == 1'b1)) === 1'b1) &&
        ((NUM_LOAD_CHANNELS > 0) === 1'b1) && (((^NUM_LOAD_CHANNELS == 1'b0) || (^NUM_LOAD_CHANNELS == 1'b1)) === 1'b1) &&
        ((NUM_STORE_CHANNELS > 0) === 1'b1) && (((^NUM_STORE_CHANNELS == 1'b0) || (^NUM_STORE_CHANNELS == 1'b1)) === 1'b1) &&
        ((NUM_SCRATCHPAD_CLIENTS > 0) === 1'b1) && (((^NUM_SCRATCHPAD_CLIENTS == 1'b0) || (^NUM_SCRATCHPAD_CLIENTS == 1'b1)) === 1'b1) &&
        ((NUM_DMA_INGRESS_CHANNELS > 0) === 1'b1) && (((^NUM_DMA_INGRESS_CHANNELS == 1'b0) || (^NUM_DMA_INGRESS_CHANNELS == 1'b1)) === 1'b1) &&
        ((NUM_DMA_EGRESS_CHANNELS > 0) === 1'b1) && (((^NUM_DMA_EGRESS_CHANNELS == 1'b0) || (^NUM_DMA_EGRESS_CHANNELS == 1'b1)) === 1'b1) &&
        ((CONTEXT_DEPTH > 0) === 1'b1) && (((^CONTEXT_DEPTH == 1'b0) || (^CONTEXT_DEPTH == 1'b1)) === 1'b1) &&
        ((CONFIG_WORD_COUNT > 0) === 1'b1) && (((^CONFIG_WORD_COUNT == 1'b0) || (^CONFIG_WORD_COUNT == 1'b1)) === 1'b1) &&
        ((COMMAND_QUEUE_DEPTH > 0) === 1'b1) && (((^COMMAND_QUEUE_DEPTH == 1'b0) || (^COMMAND_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((READ_DATA_FIFO_DEPTH > 0) === 1'b1) && (((^READ_DATA_FIFO_DEPTH == 1'b0) || (^READ_DATA_FIFO_DEPTH == 1'b1)) === 1'b1) &&
        ((WRITE_DATA_FIFO_DEPTH > 0) === 1'b1) && (((^WRITE_DATA_FIFO_DEPTH == 1'b0) || (^WRITE_DATA_FIFO_DEPTH == 1'b1)) === 1'b1) &&
        ((COMPLETION_QUEUE_DEPTH > 0) === 1'b1) && (((^COMPLETION_QUEUE_DEPTH == 1'b0) || (^COMPLETION_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((EVENT_QUEUE_DEPTH > 0) === 1'b1) && (((^EVENT_QUEUE_DEPTH == 1'b0) || (^EVENT_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((MAX_OUTSTANDING_READS > 0) === 1'b1) && (((^MAX_OUTSTANDING_READS == 1'b0) || (^MAX_OUTSTANDING_READS == 1'b1)) === 1'b1) &&
        ((MAX_OUTSTANDING_WRITES > 0) === 1'b1) && (((^MAX_OUTSTANDING_WRITES == 1'b0) || (^MAX_OUTSTANDING_WRITES == 1'b1)) === 1'b1) &&
        ((COUNT_WIDTH > 0) === 1'b1) && (((^COUNT_WIDTH == 1'b0) || (^COUNT_WIDTH == 1'b1)) === 1'b1) &&
        ((MAX_ELEMENT_BYTES > 0) === 1'b1) && (((^MAX_ELEMENT_BYTES == 1'b0) || (^MAX_ELEMENT_BYTES == 1'b1)) === 1'b1) &&
        ((NUM_PROTECTION_REGIONS > 0) === 1'b1) && (((^NUM_PROTECTION_REGIONS == 1'b0) || (^NUM_PROTECTION_REGIONS == 1'b1)) === 1'b1) &&
        ((NUM_BUFFER_ROLES > 0) === 1'b1) && (((^NUM_BUFFER_ROLES == 1'b0) || (^NUM_BUFFER_ROLES == 1'b1)) === 1'b1) &&
        ((NUM_EVENTS > 0) === 1'b1) && (((^NUM_EVENTS == 1'b0) || (^NUM_EVENTS == 1'b1)) === 1'b1) &&
        ((OWNER_ID_WIDTH > 0) === 1'b1) && (((^OWNER_ID_WIDTH == 1'b0) || (^OWNER_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((KERNEL_ID_WIDTH > 0) === 1'b1) && (((^KERNEL_ID_WIDTH == 1'b0) || (^KERNEL_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((PACKAGE_ID_WIDTH > 0) === 1'b1) && (((^PACKAGE_ID_WIDTH == 1'b0) || (^PACKAGE_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((CONTEXT_VERSION_WIDTH > 0) === 1'b1) && (((^CONTEXT_VERSION_WIDTH == 1'b0) || (^CONTEXT_VERSION_WIDTH == 1'b1)) === 1'b1) &&
        ((COMMAND_ID_WIDTH > 0) === 1'b1) && (((^COMMAND_ID_WIDTH == 1'b0) || (^COMMAND_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((DESCRIPTOR_GENERATION_WIDTH > 0) === 1'b1) && (((^DESCRIPTOR_GENERATION_WIDTH == 1'b0) || (^DESCRIPTOR_GENERATION_WIDTH == 1'b1)) === 1'b1) &&
        ((ALLOCATION_GENERATION_WIDTH > 0) === 1'b1) && (((^ALLOCATION_GENERATION_WIDTH == 1'b0) || (^ALLOCATION_GENERATION_WIDTH == 1'b1)) === 1'b1) &&
        ((EXECUTION_EPOCH_WIDTH > 0) === 1'b1) && (((^EXECUTION_EPOCH_WIDTH == 1'b0) || (^EXECUTION_EPOCH_WIDTH == 1'b1)) === 1'b1) &&
        ((SPACE_ID_WIDTH > 0) === 1'b1) && (((^SPACE_ID_WIDTH == 1'b0) || (^SPACE_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((STREAM_ID_WIDTH > 0) === 1'b1) && (((^STREAM_ID_WIDTH == 1'b0) || (^STREAM_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((REGION_ID_WIDTH > 0) === 1'b1) && (((^REGION_ID_WIDTH == 1'b0) || (^REGION_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((BUFFER_ID_WIDTH > 0) === 1'b1) && (((^BUFFER_ID_WIDTH == 1'b0) || (^BUFFER_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((DATATYPE_WIDTH > 0) === 1'b1) && (((^DATATYPE_WIDTH == 1'b0) || (^DATATYPE_WIDTH == 1'b1)) === 1'b1) &&
        ((PRIORITY_WIDTH > 0) === 1'b1) && (((^PRIORITY_WIDTH == 1'b0) || (^PRIORITY_WIDTH == 1'b1)) === 1'b1) &&
        ((TRANSFER_TIMEOUT_CYCLES > 0) === 1'b1) && (((^TRANSFER_TIMEOUT_CYCLES == 1'b0) || (^TRANSFER_TIMEOUT_CYCLES == 1'b1)) === 1'b1) &&
        ((CANCEL_TIMEOUT_CYCLES > 0) === 1'b1) && (((^CANCEL_TIMEOUT_CYCLES == 1'b0) || (^CANCEL_TIMEOUT_CYCLES == 1'b1)) === 1'b1) &&
        ((TILE_ID_WIDTH > 0) === 1'b1) && (((^TILE_ID_WIDTH == 1'b0) || (^TILE_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((ARCH_VERSION_WIDTH > 0) === 1'b1) && (((^ARCH_VERSION_WIDTH == 1'b0) || (^ARCH_VERSION_WIDTH == 1'b1)) === 1'b1) &&
        ((CAPABILITY_ID_WIDTH > 0) === 1'b1) && (((^CAPABILITY_ID_WIDTH == 1'b0) || (^CAPABILITY_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((PREDICATE_WIDTH > 0) === 1'b1) && (((^PREDICATE_WIDTH == 1'b0) || (^PREDICATE_WIDTH == 1'b1)) === 1'b1) &&
        ((PREDICATE_METADATA_WIDTH > 0) === 1'b1) && (((^PREDICATE_METADATA_WIDTH == 1'b0) || (^PREDICATE_METADATA_WIDTH == 1'b1)) === 1'b1) &&
        ((CONFIG_DATA_WIDTH > 0) === 1'b1) && (((^CONFIG_DATA_WIDTH == 1'b0) || (^CONFIG_DATA_WIDTH == 1'b1)) === 1'b1) &&
        ((CONTEXT_CHECKSUM_WIDTH > 0) === 1'b1) && (((^CONTEXT_CHECKSUM_WIDTH == 1'b0) || (^CONTEXT_CHECKSUM_WIDTH == 1'b1)) === 1'b1) &&
        ((CONFIG_QUEUE_DEPTH > 0) === 1'b1) && (((^CONFIG_QUEUE_DEPTH == 1'b0) || (^CONFIG_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((RUNTIME_TAG_WIDTH > 0) === 1'b1) && (((^RUNTIME_TAG_WIDTH == 1'b0) || (^RUNTIME_TAG_WIDTH == 1'b1)) === 1'b1) &&
        ((STALL_REASON_WIDTH > 0) === 1'b1) && (((^STALL_REASON_WIDTH == 1'b0) || (^STALL_REASON_WIDTH == 1'b1)) === 1'b1) &&
        ((ERROR_CODE_WIDTH > 0) === 1'b1) && (((^ERROR_CODE_WIDTH == 1'b0) || (^ERROR_CODE_WIDTH == 1'b1)) === 1'b1) &&
        ((TRACE_WIDTH > 0) === 1'b1) && (((^TRACE_WIDTH == 1'b0) || (^TRACE_WIDTH == 1'b1)) === 1'b1) &&
        ((EVENT_WIDTH > 0) === 1'b1) && (((^EVENT_WIDTH == 1'b0) || (^EVENT_WIDTH == 1'b1)) === 1'b1) &&
        ((DATA_METADATA_WIDTH > 0) === 1'b1) && (((^DATA_METADATA_WIDTH == 1'b0) || (^DATA_METADATA_WIDTH == 1'b1)) === 1'b1) &&
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
        ((TILE_ID >= 0) === 1'b1) && (((^TILE_ID == 1'b0) || (^TILE_ID == 1'b1)) === 1'b1) &&
        ((INPUT_BUFFER_DEPTH >= 0) === 1'b1) && (((^INPUT_BUFFER_DEPTH == 1'b0) || (^INPUT_BUFFER_DEPTH == 1'b1)) === 1'b1) &&
        ((OUTPUT_BUFFER_DEPTH >= 0) === 1'b1) && (((^OUTPUT_BUFFER_DEPTH == 1'b0) || (^OUTPUT_BUFFER_DEPTH == 1'b1)) === 1'b1) &&
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
    input wire i_clock_enable,
    input wire i_launch,
    input wire i_release,
    input wire i_cancel,
    input wire i_flush,
    input wire i_copy_worker,
    input wire [DESC-1:0] i_descriptor,
    input wire i_source_valid,
    output wire o_source_ready,
    output wire o_source_admit,
    input wire [D-1:0] i_source_data,
    input wire [M-1:0] i_source_metadata,
    input wire i_source_commit,
    input wire [SY-1:0] i_source_commit_keep,
    output wire o_sink_valid,
    input wire i_sink_ready,
    output wire [D-1:0] o_sink_data,
    output wire [M-1:0] o_sink_metadata,
    input wire i_sink_commit,
    input wire [SY-1:0] i_sink_commit_keep,
    input wire i_copy_valid,
    output wire o_copy_ready,
    input wire [ED-1:0] i_copy_data,
    input wire i_copy_error,
    output wire o_copy_valid,
    input wire i_copy_ready,
    output wire [ED-1:0] o_copy_data,
    output wire o_copy_error,
    output wire o_memory_valid,
    input wire i_memory_ready,
    output wire [A-1:0] o_memory_address,
    output wire [MSZ-1:0] o_memory_size,
    output wire [MD-1:0] o_memory_data,
    output wire [MY-1:0] o_memory_strobe,
    output wire [AT-1:0] o_memory_tag,
    input wire i_response_valid,
    output wire o_response_ready,
    input wire [AT-1:0] i_response_tag,
    input wire [IDW-1:0] i_response_identity,
    input wire [MD-1:0] i_response_data,
    input wire i_response_error,
    input wire [MBW-1:0] i_response_committed,
    output wire o_done,
    output wire o_stopping,
    output wire o_fatal,
    output wire [7:0] o_code,
    output wire [BC-1:0] o_bytes_read,
    output wire [BC-1:0] o_bytes_written,
    output wire [2*C-1:0] o_elements,
    output wire [31:0] o_outstanding,
    output wire o_progress,
    output wire o_overflow,
    output wire o_saturated,
    output wire o_started,
    output wire o_request_accepted,
    output wire o_response_accepted,
    output wire o_input_accepted,
    output wire o_output_accepted
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

    typedef struct packed {
        logic [3:0] phase;
        logic copy_worker;
        logic stopping;
        logic fatal;
        logic engine_done;
        logic input_done;
        logic output_done;
        logic [7:0] code;
        logic [TW-1:0] timer;
        logic [CT-1:0] cancel_timer;
        logic [BC-1:0] source_bytes;
        logic [BC-1:0] sink_bytes;
        logic [2*C+LOG:0] source_beats;
        logic [2*C+LOG:0] sink_beats;
        logic [2*C+LOG:0] produced_beats;
        logic [2*C+LOG:0] consumed_beats;
        logic [2*C-1:0] write_elements;
        logic [2*C-1:0] copy_positions;
        logic [2*C-1:0] store_positions;
    } mst_channel_control_t;

    descriptor_t d;
    wire [DESC-1:0] stored_descriptor;
    mst_channel_control_t q;
    mst_channel_control_t n;
    wire descriptor_bad;
    wire control_bad;
    wire run = i_rstb === 1'b1;
    wire reserving = q.phase == MST_CMD_RESERVING;
    wire active = q.phase == MST_CMD_ACTIVE;
    wire stopping = q.stopping || i_cancel === 1'b1 || i_flush === 1'b1;
    wire local_reset = run && q.phase != MST_CMD_FREE && q.phase != MST_CMD_COMPLETING;
    wire issue = active && i_clock_enable === 1'b1 &&!stopping &&!q.fatal;
    wire load_memory = IS_LOAD == 1 && memory_source(d.mode.transfer);
    wire store_memory = IS_LOAD == 0 && memory_destination(d.mode.transfer);
    wire copy_source = IS_LOAD == 1 && d.mode.transfer == MST_LOCAL_COPY;
    wire stream_source =!load_memory &&!q.copy_worker;
    wire stream_sink =!store_memory &&!copy_source;
    wire [SZ-1:0] source_size = d.format.source_log2 + d.format.lane_log2;
    wire [SZ-1:0] destination_size = d.format.destination_log2 + d.format.lane_log2;
    wire [2*C-1:0] positions = (2 * C)'(d.control.inner_count) * (2 * C)'(d.control.outer_count);
    wire [LOG:0] source_chunks = (LOG + 1)'(((64'd1 << source_size) + SY - 1) / SY);
    wire [LOG:0] destination_chunks = (LOG + 1)'(((64'd1 << destination_size) + SY - 1) / SY);
    wire [2*C+LOG:0] source_frame = (2 * C + LOG + 1)'(positions) * source_chunks;
    wire [2*C+LOG:0] source_row = (2 * C + LOG + 1)'(d.control.inner_count) * source_chunks;
    wire [2*C+LOG:0] destination_frame = (2 * C + LOG + 1)'(positions) * destination_chunks;
    wire [2*C+LOG:0] destination_row = (2 * C + LOG + 1)'(d.control.inner_count) *
        destination_chunks;
    wire [TW-1:0] timeout_limit = d.control.timeout == 0 ? TW'(TRANSFER_TIMEOUT_CYCLES) :
        d.control.timeout;
    wire [SZ-1:0] engine_size = IS_LOAD == 1 ? source_size : destination_size;
    wire engine_config_ready;
    wire engine_out_valid;
    wire engine_out_ready;
    wire [ED-1:0] engine_out_data;
    wire [EY-1:0] engine_out_keep;
    wire engine_out_first;
    wire engine_out_last;
    wire engine_out_error;
    wire engine_in_valid;
    wire engine_in_ready;
    wire [ED-1:0] engine_in_data;
    wire [EY-1:0] engine_in_keep;
    wire engine_in_first;
    wire engine_in_last;
    wire engine_in_error;
    wire engine_completed;
    wire engine_failed;
    wire engine_memory_error;
    wire engine_error;
    wire [31:0] engine_outstanding;
    wire engine_request_valid;
    wire engine_request_ready;
    wire [SI-1:0] engine_request_tag;
    wire [ED-1:0] engine_request_data;
    wire engine_response_valid;
    wire engine_response_ready;
    wire [SI-1:0] engine_response_tag;
    wire [ED-1:0] engine_response_data;
    wire engine_response_error;
    wire [A-1:0] real_address;
    wire real_valid;
    wire real_config_ready;
    wire real_error;
    wire [BC-1:0] adapter_bytes;
    wire adapter_idle;
    wire adapter_error;
    wire [7:0] adapter_code;
    wire adapter_progress;
    wire [$clog2((IS_LOAD == 1 ? MAX_OUTSTANDING_READS : MAX_OUTSTANDING_WRITES)+1)-1:0]
        adapter_outstanding;
    endpoint_t memory_endpoint;
    assign memory_endpoint = IS_LOAD == 1 ? d.source : d.destination;
    assign d = stored_descriptor;

    banked_scratchpad_state #(
        .WIDTH(DESC),
        .PROTECTION(COMMAND_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_descriptor (
        .i_clk(i_clk),
        .i_reset_n(i_rstb),
        .i_data(i_launch ? i_descriptor : stored_descriptor),
        .o_data(stored_descriptor),
        .o_bad(descriptor_bad)
    );

    banked_scratchpad_state #(
        .WIDTH($bits(mst_channel_control_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_control (
        .i_clk(i_clk),
        .i_reset_n(i_rstb),
        .i_data(n),
        .o_data(q),
        .o_bad(control_bad)
    );

    // Engines use a naturally aligned synthetic linear space. The real AGU runs
    // the validated signed affine pattern with byte alignment. Logical handshakes
    // advance both exactly once; the adapter owns physical word fragments.
    agu #(
        .ADDR_WIDTH(A),
        .COUNT_WIDTH(C),
        .MAX_ELEMENT_BYTES(EY),
        .SPACE_ID_WIDTH(SP),
        .CHANNEL_ID_WIDTH(CH),
        .CONTEXT_ID_WIDTH(CI),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_address (
        .i_clk(i_clk),
        .i_rstb(local_reset),
        .i_error_clear(1'b0),
        .i_config_valid(reserving && (load_memory || store_memory)),
        .o_config_ready(real_config_ready),
        .i_mode(d.mode.address_mode == MST_ADDR_STRIDED_2D ? 2'b10 : 2'b01),
        .i_base_address(memory_endpoint.base),
        .i_inner_count(C'(d.control.inner_count)),
        .i_outer_count(C'(d.control.outer_count)),
        .i_inner_stride(d.mode.address_mode == MST_ADDR_LINEAR ?
            A'(64'd1 << engine_size) : memory_endpoint.inner_stride),
        .i_outer_stride(memory_endpoint.outer_stride),
        .i_element_size_log2({SZ{1'b0}}),
        .i_is_write(IS_LOAD == 0),
        .i_address_space(memory_endpoint.space),
        .i_channel_id(memory_endpoint.channel),
        .i_context_id(CI'(d.identity.context_id)),
        .i_emit_end_of_stream(1'(d.format.eos)),
        .o_valid(real_valid),
        .i_ready(engine_request_valid && engine_request_ready),
        .o_address(real_address),
        .o_inner_index(),
        .o_outer_index(),
        .o_first(),
        .o_last(),
        .o_row_first(),
        .o_row_last(),
        .o_end_of_stream(),
        .o_element_size_log2(),
        .o_is_write(),
        .o_address_space(),
        .o_channel_id(),
        .o_context_id(),
        .o_idle(),
        .o_active(),
        .o_descriptor_started(),
        .o_address_accepted(),
        .o_completed(),
        .o_addresses_accepted(),
        .o_error(real_error),
        .o_error_code()
    );

    if (IS_LOAD == 1) begin : g_load
        wire [$clog2(MAX_OUTSTANDING_READS+1)-1:0] outstanding;

        load_engine #(
            .ADDR_WIDTH(VW),
            .DATA_WIDTH(ED),
            .COUNT_WIDTH(VC),
            .MAX_ELEMENT_BYTES(EY),
            .MAX_OUTSTANDING(MAX_OUTSTANDING_READS),
            .SPACE_ID_WIDTH(SP),
            .CHANNEL_ID_WIDTH(CH),
            .CONTEXT_ID_WIDTH(CI),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_engine (
            .i_clk(i_clk),
            .i_rstb(local_reset),
            .i_error_clear(1'b0),
            .i_config_valid(reserving && load_memory),
            .o_config_ready(engine_config_ready),
            .i_mode(2'b00),
            .i_base_address({VW{1'b0}}),
            .i_inner_count(positions),
            .i_outer_count(VC'(1)),
            .i_inner_stride({VW{1'b0}}),
            .i_outer_stride({VW{1'b0}}),
            .i_element_size_log2(engine_size),
            .i_address_space(memory_endpoint.space),
            .i_channel_id(memory_endpoint.channel),
            .i_context_id(CI'(d.identity.context_id)),
            .i_emit_end_of_stream(1'(d.format.eos)),
            .o_mem_req_valid(engine_request_valid),
            .i_mem_req_ready(engine_request_ready),
            .o_mem_req_address(),
            .o_mem_req_size_log2(),
            .o_mem_req_tag(engine_request_tag),
            .o_mem_req_address_space(),
            .o_mem_req_channel_id(),
            .o_mem_req_context_id(),
            .i_mem_rsp_valid(engine_response_valid),
            .o_mem_rsp_ready(engine_response_ready),
            .i_mem_rsp_tag(engine_response_tag),
            .i_mem_rsp_error(engine_response_error),
            .i_mem_rsp_data(engine_response_data),
            .o_stream_valid(engine_out_valid),
            .i_stream_ready(engine_out_ready),
            .o_stream_data(engine_out_data),
            .o_stream_keep(engine_out_keep),
            .o_stream_first(engine_out_first),
            .o_stream_last(engine_out_last),
            .o_stream_error(engine_out_error),
            .o_stream_row_first(),
            .o_stream_row_last(),
            .o_stream_end_of_stream(),
            .o_stream_channel_id(),
            .o_stream_context_id(),
            .o_idle(),
            .o_busy(),
            .o_command_started(),
            .o_request_accepted(),
            .o_response_accepted(),
            .o_stream_accepted(),
            .o_command_completed(engine_completed),
            .o_completed_with_error(),
            .o_command_failed(engine_failed),
            .o_outstanding(outstanding),
            .o_memory_error_seen(engine_memory_error),
            .o_error(engine_error),
            .o_error_code()
        );

        assign engine_outstanding = 32'(outstanding);
        assign engine_request_data = '0;
        assign engine_in_ready = 1'b0;
    end
    if (IS_LOAD == 0) begin : g_store
        wire [$clog2(MAX_OUTSTANDING_WRITES+1)-1:0] outstanding;

        store_engine #(
            .ADDR_WIDTH(VW),
            .DATA_WIDTH(ED),
            .COUNT_WIDTH(VC),
            .MAX_ELEMENT_BYTES(EY),
            .MAX_OUTSTANDING(MAX_OUTSTANDING_WRITES),
            .SPACE_ID_WIDTH(SP),
            .CHANNEL_ID_WIDTH(CH),
            .CONTEXT_ID_WIDTH(CI),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_engine (
            .i_clk(i_clk),
            .i_rstb(local_reset),
            .i_error_clear(1'b0),
            .i_config_valid(reserving && store_memory),
            .o_config_ready(engine_config_ready),
            .i_mode(2'b00),
            .i_base_address({VW{1'b0}}),
            .i_inner_count(positions),
            .i_outer_count(VC'(1)),
            .i_inner_stride({VW{1'b0}}),
            .i_outer_stride({VW{1'b0}}),
            .i_element_size_log2(engine_size),
            .i_address_space(memory_endpoint.space),
            .i_channel_id(memory_endpoint.channel),
            .i_context_id(CI'(d.identity.context_id)),
            .i_expect_end_of_stream(1'(d.format.eos)),
            .o_mem_req_valid(engine_request_valid),
            .i_mem_req_ready(engine_request_ready),
            .o_mem_req_address(),
            .o_mem_req_size_log2(),
            .o_mem_req_tag(engine_request_tag),
            .o_mem_req_address_space(),
            .o_mem_req_channel_id(),
            .o_mem_req_context_id(),
            .i_mem_rsp_valid(engine_response_valid),
            .o_mem_rsp_ready(engine_response_ready),
            .i_mem_rsp_tag(engine_response_tag),
            .i_mem_rsp_error(engine_response_error),
            .o_mem_req_data(engine_request_data),
            .o_mem_req_strobe(),
            .i_stream_valid(engine_in_valid),
            .o_stream_ready(engine_in_ready),
            .i_stream_data(engine_in_data),
            .i_stream_keep(engine_in_keep),
            .i_stream_first(engine_in_first),
            .i_stream_last(engine_in_last),
            .i_stream_row_first(engine_in_first),
            .i_stream_row_last(engine_in_last),
            .i_stream_end_of_stream(d.format.eos && engine_in_last),
            .i_stream_channel_id(memory_endpoint.channel),
                .i_stream_context_id(CI'(d.identity.context_id)),
            .i_stream_error(engine_in_error),
            .o_response_retired(),
            .o_idle(),
            .o_busy(),
            .o_command_started(),
            .o_request_accepted(),
            .o_response_accepted(),
            .o_stream_accepted(),
            .o_command_completed(engine_completed),
            .o_completed_with_error(),
            .o_command_failed(engine_failed),
            .o_outstanding(outstanding),
            .o_memory_error_seen(engine_memory_error),
            .o_error(engine_error),
            .o_error_code()
        );

        assign engine_outstanding = 32'(outstanding);
        assign engine_out_valid = 1'b0;
        assign engine_out_data = '0;
        assign engine_out_keep = '0;
        assign engine_out_first = 1'b0;
        assign engine_out_last = 1'b0;
        assign engine_out_error = 1'b0;
    end

    mst_fragment_adapter #(
        .ADDR_WIDTH(A),
        .ELEMENT_DATA_WIDTH(ED),
        .MEMORY_DATA_WIDTH(MD),
        .MAX_OUTSTANDING(IS_LOAD == 1 ?
            MAX_OUTSTANDING_READS : MAX_OUTSTANDING_WRITES),
        .SLOT_WIDTH(SI),
        .GENERATION_WIDTH(SG),
        .BYTE_COUNT_WIDTH(BC),
        .EPOCH_WIDTH(EP),
            .IDENTITY_WIDTH(IDW),
        .WRITE(IS_LOAD == 0),
        .PROTECTION(CONTROL_PROTECTION > FIFO_PROTECTION ?
            CONTROL_PROTECTION : FIFO_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
    ) u_fragments (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_clear(q.phase == MST_CMD_FREE),
        .i_cancel(stopping),
        .i_issue_enable(issue),
        .i_epoch(EP'(d.identity.epoch)),
        .i_identity(d.identity),
        .i_logical_valid(engine_request_valid && real_valid && issue),
        .o_logical_ready(engine_request_ready),
        .i_logical_address(real_address),
        .i_logical_size(engine_size),
        .i_logical_tag(engine_request_tag),
        .i_logical_data(engine_request_data),
        .o_logical_response_valid(engine_response_valid),
        .i_logical_response_ready(engine_response_ready),
            .o_logical_response_tag(engine_response_tag),
        .o_logical_response_data(engine_response_data),
            .o_logical_response_error(engine_response_error),
        .o_memory_valid(o_memory_valid),
        .i_memory_ready(i_memory_ready),
        .o_memory_address(o_memory_address),
        .o_memory_size(o_memory_size),
        .o_memory_data(o_memory_data),
        .o_memory_strobe(o_memory_strobe),
        .o_memory_tag(o_memory_tag),
        .i_response_valid(i_response_valid),
        .o_response_ready(o_response_ready),
        .i_response_tag(i_response_tag),
        .i_response_identity(i_response_identity),
        .i_response_data(i_response_data),
        .i_response_error(i_response_error),
        .i_response_committed(i_response_committed),
        .o_outstanding(adapter_outstanding),
        .o_bytes(adapter_bytes),
        .o_progress(adapter_progress),
        .o_idle(adapter_idle),
        .o_error(adapter_error),
        .o_error_code(adapter_code)
    );

    wire [D+M-1:0] input_packet;
    wire input_valid;
    wire input_ready;
    wire [31:0] input_count;
    wire input_bad;
    wire input_fifo_ready;
    stream_t input_metadata;
    assign input_metadata = input_packet[D+:STREAM_BITS];

    tile_shell_queue #(
        .WIDTH(D + M),
        .DEPTH(WRITE_DATA_FIFO_DEPTH),
        .PROTECTION(FIFO_PROTECTION)
    ) u_input (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(stopping),
        .i_admit(issue && stream_source),
        .i_deliver(active && stream_source),
        .i_valid(i_source_valid),
        .o_ready(input_fifo_ready),
        .i_data({i_source_metadata, i_source_data}),
        .o_valid(input_valid),
        .i_ready(input_ready),
        .o_data(input_packet),
        .o_count(input_count),
        .o_bad(input_bad),
        .o_corrected()
    );

    // Once top-level admission stops, already buffered shell inputs can drain
    // into cancellation accounting. DMA sources have no shell holding queue.
    assign o_source_ready = stream_source && (stopping ? run : input_fifo_ready);
    assign o_source_admit = stream_source && issue && q.source_beats < source_frame;
    wire input_format_config_ready;
    wire input_format_valid;
    wire input_format_ready;
    wire [D-1:0] input_format_data;
    wire [SY-1:0] input_format_keep;
    wire input_format_error;
    wire input_format_complete;
    wire input_format_bad;
    wire input_format_busy;
    wire [2*C+LOG:0] input_beats;
    wire [2*C+LOG:0] input_emitted;
    logic [SY-1:0] expected_input_keep;
    wire identity_matches = input_metadata.identity === d.identity &&
        input_metadata.version === d.identity.version &&
        input_metadata.context_id === d.identity.context_id &&
        input_metadata.element_log2 === d.format.source_log2 &&
        input_metadata.lane_log2 === d.format.lane_log2;
    wire input_header_error =!identity_matches || input_metadata.keep !== expected_input_keep ||
        input_metadata.lanes !== expected_input_keep;

    always @* begin
        expected_input_keep = '0;

        for (int b = 0; b < SY; b++) begin
            if (64'(b) + (64'(input_beats) % 64'(source_chunks == 0 ? 1 : source_chunks)) * SY <
                (64'd1 << source_size)) expected_input_keep[b] = 1'b1;
        end
    end

    stream_formatter #(
        .DATA_WIDTH(D),
        .NUM_LANES(SY),
        .COUNT_WIDTH(2 * C + LOG + 1),
        .DATATYPE_WIDTH(DT),
        .CHANNEL_ID_WIDTH(ST),
        .CONTEXT_ID_WIDTH(CI),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_input_formatter (
        .i_clk(i_clk),
        .i_rstb(local_reset),
        .i_flush(stopping),
        .i_error_clear(1'b0),
        .i_config_valid(reserving && stream_source),
        .o_config_ready(input_format_config_ready),
        .i_mode(1'b1),
        .i_frame_beats(source_frame),
        .i_row_beats(source_row),
        .i_lane_enable({SY{1'b1}}),
        .i_datatype(DT'(d.format.datatype)),
        .i_channel_id(ST'(d.source.channel)),
        .i_context_id(CI'(d.identity.context_id)),
        .i_emit_end_of_stream(1'(d.format.eos)),
        .i_valid(input_valid),
        .o_ready(input_ready),
        .i_data(input_packet[0+:D]),
        .i_keep(input_metadata.keep),
        .i_lane_mask(input_metadata.lanes),
        .i_first(input_metadata.first),
        .i_last(input_metadata.last),
        .i_row_first(input_metadata.row_first),
        .i_row_last(input_metadata.row_last),
        .i_end_of_stream(input_metadata.eos),
        .i_stream_datatype(input_metadata.datatype),
        .i_stream_channel_id(input_metadata.channel),
        .i_stream_context_id(input_metadata.context_id),
        .i_error(input_metadata.error || input_header_error),
        .o_valid(input_format_valid),
        .i_ready(input_format_ready),
        .o_data(input_format_data),
        .o_keep(input_format_keep),
        .o_lane_mask(),
        .o_first(),
        .o_last(),
        .o_row_first(),
        .o_row_last(),
        .o_end_of_stream(),
        .o_datatype(),
        .o_channel_id(),
        .o_context_id(),
        .o_stream_error(input_format_error),
        .o_format_error_code(),
        .o_idle(),
        .o_busy(input_format_busy),
        .o_frame_started(),
        .o_input_accepted(),
        .o_output_accepted(),
        .o_frame_completed(input_format_complete),
        .o_completed_with_error(),
        .o_frame_aborted(),
        .o_beats_accepted(input_beats),
        .o_beats_emitted(input_emitted),
        .o_format_error_seen(),
        .o_input_error_seen(),
        .o_error(input_format_bad),
        .o_config_error_code()
    );

    wire input_converter_ready;
    wire input_converter_valid;
    wire input_converter_accept;
    wire [ED-1:0] input_converter_data;
    wire [EY-1:0] input_converter_keep;
    wire input_converter_busy;
    assign input_format_ready = stopping || input_format_error || input_converter_ready;

    width_converter #(
        .IN_WIDTH(D),
        .OUT_WIDTH(ED),
        .USER_WIDTH(1),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_input_width (
        .i_clk(i_clk),
        .i_rstb(local_reset),
        .i_flush(stopping),
        .i_valid(input_format_valid &&!input_format_error && issue),
        .o_ready(input_converter_ready),
        .i_data(input_format_data),
        .i_keep(input_format_keep),
        .i_last((64'(input_emitted) + 1) %
            64'(source_chunks == 0 ? 1 : source_chunks) == 0),
        .i_user(1'b0),
        .o_valid(input_converter_valid),
        .i_ready(input_converter_accept),
        .o_data(input_converter_data),
        .o_keep(input_converter_keep),
        .o_last(),
        .o_user(),
        .o_busy(input_converter_busy)
    );

    wire pack_valid;
    wire pack_ready;
    wire pack_input_ready;
    wire [ED-1:0] pack_data;
    wire pack_overflow;
    wire pack_saturated;
    wire pack_bad;
    wire source_valid = load_memory ? engine_out_valid : input_converter_valid;
    wire [ED-1:0] source_data = load_memory ? engine_out_data : input_converter_data;
    wire source_error = load_memory && engine_out_error;
    assign engine_out_ready = stopping || source_error || (pack_input_ready && issue);
    assign input_converter_accept = stopping || (pack_input_ready && issue);

    mst_element_converter #(
        .DATA_WIDTH(ED),
        .SUPPORT_CONVERSION(SUPPORT_ELEMENT_CONVERSION)
    ) u_pack (
        .i_clk(i_clk),
        .i_rstb(local_reset),
        .i_valid(source_valid && issue && !source_error),
        .o_ready(pack_input_ready),
        .i_data(source_data),
        .i_source_log2(SZ'(d.format.source_log2)),
        .i_destination_log2(SZ'(d.format.destination_log2)),
        .i_lane_log2(SZ'(d.format.lane_log2)),
        .i_signed(1'(d.format.signed_mode)),
        .i_saturate(1'(d.format.saturate)), .i_reverse(1'(d.format.reverse)),
        .o_valid(pack_valid), .i_ready(pack_ready), .o_data(pack_data),
        .o_overflow(pack_overflow), .o_saturated(pack_saturated), .o_error(pack_bad)
    );

    wire [EY-1:0] destination_keep = EY'(({{EY{1'b0}}, 1'b1} <<
        (64'd1 << destination_size)) - 1'b1);
    assign engine_in_valid = store_memory && issue && (q.copy_worker ? i_copy_valid : pack_valid);
    assign engine_in_data = q.copy_worker ? i_copy_data : pack_data;
    assign engine_in_keep = destination_keep;
    assign engine_in_first = q.store_positions == 0;
    assign engine_in_last = q.store_positions == positions - 1'b1;
    assign engine_in_error = q.copy_worker && i_copy_error;
    assign o_copy_ready = store_memory && q.copy_worker && issue && engine_in_ready;

    wire copy_queue_ready;
    wire [31:0] copy_count;
    wire copy_bad;
    wire [ED:0] copy_packet;

    tile_shell_queue #(
        .WIDTH(ED + 1),
        .DEPTH(READ_DATA_FIFO_DEPTH),
        .PROTECTION(FIFO_PROTECTION)
    ) u_copy (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(stopping),
        .i_admit(issue && copy_source),
        .i_deliver(active && copy_source && i_clock_enable === 1'b1),
        .i_valid(pack_valid),
        .o_ready(copy_queue_ready),
        .i_data({1'b0, pack_data}),
        .o_valid(o_copy_valid),
        .i_ready(i_copy_ready),
        .o_data(copy_packet),
        .o_count(copy_count),
        .o_bad(copy_bad),
        .o_corrected()
    );

    assign o_copy_data = copy_packet[0+:ED];
    assign o_copy_error = copy_packet[ED];
    wire output_converter_ready;
    wire output_converter_valid;
    wire output_converter_accept;
    wire [D-1:0] output_converter_data;
    wire [SY-1:0] output_converter_keep;
    wire output_converter_busy;
    assign pack_ready = copy_source ? copy_queue_ready : store_memory ? engine_in_ready :
        output_converter_ready;

    width_converter #(
        .IN_WIDTH(ED),
        .OUT_WIDTH(D),
        .USER_WIDTH(1),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_output_width (
        .i_clk(i_clk),
        .i_rstb(local_reset),
        .i_flush(stopping),
        .i_valid(pack_valid && stream_sink && issue),
        .o_ready(output_converter_ready),
        .i_data(pack_data),
        .i_keep(destination_keep),
        .i_last(1'b1),
        .i_user(1'b0),
        .o_valid(output_converter_valid),
        .i_ready(output_converter_accept),
        .o_data(output_converter_data),
        .o_keep(output_converter_keep),
        .o_last(),
        .o_user(),
        .o_busy(output_converter_busy)
    );

    wire output_format_config_ready;
    wire output_format_valid;
    wire output_format_ready;
    wire [D-1:0] output_format_data;
    wire output_format_complete;
    wire output_format_busy;
    wire output_format_bad;
    stream_t output_metadata;
    wire [SY-1:0] output_keep;
    wire [SY-1:0] output_lanes;
    wire output_first;
    wire output_last;
    wire output_row_first;
    wire output_row_last;
    wire output_eos;
    wire output_error;

    always @* begin
        output_metadata = '0;
        output_metadata.context_id = d.identity.context_id;
        output_metadata.version = d.identity.version;
        output_metadata.identity = d.identity;
        output_metadata.keep = output_keep;
        output_metadata.lanes = output_lanes;
        output_metadata.datatype = d.format.datatype;
        output_metadata.channel = ST'(d.destination.channel);
        output_metadata.first = output_first;
        output_metadata.last = output_last;
        output_metadata.row_first = output_row_first;
        output_metadata.row_last = output_row_last;
        output_metadata.eos = output_eos;
        output_metadata.error = output_error;
        output_metadata.element_log2 = d.format.destination_log2;
        output_metadata.lane_log2 = d.format.lane_log2;
    end

    stream_formatter #(
        .DATA_WIDTH(D),
        .NUM_LANES(SY),
        .COUNT_WIDTH(2 * C + LOG + 1),
        .DATATYPE_WIDTH(DT),
        .CHANNEL_ID_WIDTH(ST),
        .CONTEXT_ID_WIDTH(CI),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_output_formatter (
        .i_clk(i_clk),
        .i_rstb(local_reset),
        .i_flush(stopping),
        .i_error_clear(1'b0),
        .i_config_valid(reserving && stream_sink),
        .o_config_ready(output_format_config_ready),
        .i_mode(1'b0),
        .i_frame_beats(destination_frame),
        .i_row_beats(destination_row),
        .i_lane_enable({SY{1'b1}}),
        .i_datatype(DT'(d.format.datatype)),
        .i_channel_id(ST'(d.destination.channel)),
        .i_context_id(CI'(d.identity.context_id)),
        .i_emit_end_of_stream(1'(d.format.eos)),
        .i_valid(output_converter_valid && issue),
        .o_ready(output_converter_accept),
        .i_data(output_converter_data),
        .i_keep(output_converter_keep),
        .i_lane_mask(output_converter_keep),
        .i_first(1'b0),
        .i_last(1'b0),
        .i_row_first(1'b0),
        .i_row_last(1'b0),
        .i_end_of_stream(1'b0),
        .i_stream_datatype(DT'(d.format.datatype)),
        .i_stream_channel_id(ST'(d.destination.channel)),
        .i_stream_context_id(CI'(d.identity.context_id)),
        .i_error(1'b0),
        .o_valid(output_format_valid),
        .i_ready(output_format_ready),
        .o_data(output_format_data),
        .o_keep(output_keep),
        .o_lane_mask(output_lanes),
        .o_first(output_first),
        .o_last(output_last),
        .o_row_first(output_row_first),
        .o_row_last(output_row_last),
        .o_end_of_stream(output_eos),
        .o_datatype(),
        .o_channel_id(),
        .o_context_id(),
        .o_stream_error(output_error),
        .o_format_error_code(),
        .o_idle(),
        .o_busy(output_format_busy),
        .o_frame_started(),
        .o_input_accepted(),
        .o_output_accepted(),
        .o_frame_completed(output_format_complete),
        .o_completed_with_error(),
        .o_frame_aborted(),
        .o_beats_accepted(),
        .o_beats_emitted(),
        .o_format_error_seen(),
        .o_input_error_seen(),
        .o_error(output_format_bad),
        .o_config_error_code()
    );

    wire [D+M-1:0] output_packet;
    wire [31:0] output_count;
    wire output_bad;

    tile_shell_queue #(
        .WIDTH(D + M),
        .DEPTH(READ_DATA_FIFO_DEPTH),
        .PROTECTION(FIFO_PROTECTION)
    ) u_output (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(i_flush),
        .i_admit(issue && stream_sink),
        .i_deliver(q.phase != MST_CMD_FREE && i_clock_enable === 1'b1),
        .i_valid(output_format_valid),
        .o_ready(output_format_ready),
        .i_data({M'(output_metadata), output_format_data}),
        .o_valid(o_sink_valid),
        .i_ready(i_sink_ready),
        .o_data(output_packet),
        .o_count(output_count),
        .o_bad(output_bad),
        .o_corrected()
    );

    assign o_sink_data = output_packet[0+:D];
    assign o_sink_metadata = output_packet[D+:M];
    wire output_transfer = o_sink_valid && i_sink_ready === 1'b1;
    wire engine_input_transfer = engine_in_valid && engine_in_ready;
    wire copy_transfer = o_copy_valid && i_copy_ready === 1'b1;
    wire logical_write_completed = IS_LOAD == 0 && engine_response_valid &&
        engine_response_ready &&!engine_response_error;
    wire configs_ready = (!(load_memory || store_memory) ||
        (engine_config_ready && real_config_ready)) &&
        (!stream_source || input_format_config_ready) && (!stream_sink ||
            output_format_config_ready);
    wire fatal_now = descriptor_bad || control_bad || input_bad || output_bad || copy_bad ||
        adapter_error || engine_error || real_error;
    wire progress = adapter_progress || i_source_commit || i_sink_commit ||
        (input_format_valid && input_format_ready) || (pack_valid && pack_ready) ||
        engine_input_transfer || copy_transfer || output_transfer;
    wire destination_empty = stream_sink ?
        (output_count == 0 && q.produced_beats == q.consumed_beats) :
        copy_source ? copy_count == 0 : 1'b1;
    wire normal_finished =
        (load_memory || store_memory ? q.engine_done : q.input_done) &&
        (stream_sink ? q.output_done && q.sink_beats == destination_frame :
            copy_source ? q.copy_positions == positions : q.engine_done) &&
        adapter_idle && engine_outstanding == 0 && input_count == 0 &&
!input_converter_busy &&!output_converter_busy && destination_empty;
    wire cancellation_finished = adapter_idle && engine_outstanding == 0 && destination_empty &&
        (!stream_source || i_source_valid !== 1'b1);
    assign o_done = q.phase == MST_CMD_COMPLETING;
    assign o_stopping = stopping;
    assign o_fatal = q.fatal || fatal_now;
    assign o_code = fatal_now ? (adapter_error ? adapter_code : MST_ERR_INTEGRITY) : q.code;
    assign o_bytes_read = load_memory ? adapter_bytes : q.source_bytes;
    assign o_bytes_written = store_memory ? adapter_bytes : q.sink_bytes;
    assign o_elements = store_memory ? q.write_elements :
        copy_source ? q.copy_positions : (2 * C)'(q.sink_beats /
            (destination_chunks == 0 ? 1 : destination_chunks));
    assign o_outstanding = 32'(adapter_outstanding);
    assign o_progress = progress;
    assign o_overflow = pack_valid && pack_ready && pack_overflow;
    assign o_saturated = pack_valid && pack_ready && pack_saturated;
    assign o_started = reserving && configs_ready;
    assign o_request_accepted = o_memory_valid && i_memory_ready === 1'b1;
    assign o_response_accepted = i_response_valid === 1'b1 && o_response_ready;
    assign o_input_accepted = i_source_commit;
    assign o_output_accepted = i_sink_commit;

    always @* begin
        n = q;

        if (run && i_launch === 1'b1 && q.phase == MST_CMD_FREE) begin
            n = '0;
            n.phase = MST_CMD_RESERVING;
            n.copy_worker = i_copy_worker;
        end

        if (reserving && configs_ready) n.phase = MST_CMD_ACTIVE;

        if (active || reserving) begin
            if (engine_completed) n.engine_done = 1'b1;

            if (input_format_complete) n.input_done = 1'b1;

            if (output_format_complete) n.output_done = 1'b1;

            if (copy_transfer) n.copy_positions = n.copy_positions + 1'b1;

            if (engine_input_transfer) n.store_positions = n.store_positions + 1'b1;

            if (logical_write_completed) n.write_elements = n.write_elements + 1'b1;

            if (i_source_commit) begin
                n.source_beats = n.source_beats + 1'b1;

                for (int b = 0; b < SY; b++)
                    if (i_source_commit_keep[b] === 1'b1) n.source_bytes = n.source_bytes + 1'b1;
            end

            if (i_sink_commit) begin
                n.sink_beats = n.sink_beats + 1'b1;
                n.consumed_beats = n.consumed_beats + 1'b1;

                for (int b = 0; b < SY; b++)
                    if (i_sink_commit_keep[b] === 1'b1) n.sink_bytes = n.sink_bytes + 1'b1;
            end

            if (output_transfer) n.produced_beats = n.produced_beats + 1'b1;

            if (i_flush === 1'b1) n.produced_beats = n.consumed_beats;

            if (active &&!stopping && i_clock_enable === 1'b1) begin
                if (progress) n.timer = '0;
                else if (q.timer >= timeout_limit - 1'b1) begin
                    n.stopping = 1'b1;
                    if (q.code == 0) n.code = MST_ERR_TIMEOUT;
                end else n.timer = q.timer + 1'b1;
            end

            if (stopping) begin
                n.stopping = 1'b1;

                if (n.code == 0) n.code = MST_ERR_CANCELED;

                if (cancellation_finished) n.phase = MST_CMD_COMPLETING;
                else if (q.cancel_timer >= CT'(CANCEL_TIMEOUT_CYCLES - 1)) begin
                    n.phase = MST_CMD_COMPLETING;
                    n.fatal = 1'b1;
                    n.code = MST_ERR_CONTAINMENT;
                end else n.cancel_timer = q.cancel_timer + 1'b1;
            end else if (normal_finished) n.phase = MST_CMD_COMPLETING;

            if ((input_format_valid && input_format_error) || pack_bad || input_format_bad ||
                output_format_bad || source_error || (q.copy_worker && i_copy_valid && i_copy_error)
                    ||
                engine_failed || engine_memory_error) begin
                n.stopping = 1'b1;

                if (n.code == 0) n.code = source_error || engine_memory_error ?
                    MST_ERR_MEMORY : MST_ERR_FORMAT;
            end

            if (fatal_now) begin
                n.fatal = 1'b1;
                n.stopping = 1'b1;

                if (n.code == 0) n.code = adapter_error ? adapter_code : MST_ERR_INTEGRITY;
            end
        end

        if (run && i_release === 1'b1 && o_done &&!q.fatal &&!fatal_now) n = '0;
    end
endmodule
`default_nettype wire
