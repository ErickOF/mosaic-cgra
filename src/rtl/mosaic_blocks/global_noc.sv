`timescale 1ns / 1ps
`default_nettype none

// Generated dimensions are immutable. The dedicated configuration port owns
// inactive flow/fault images; runtime traffic crosses actual TNI/router RTL.
module global_noc #(
    parameter NOC_X = 2,
    parameter NOC_Y = 2,
    parameter NUM_ROUTERS = NOC_X * NOC_Y,
    parameter NUM_ENDPOINTS = NUM_ROUTERS,
    parameter NOC_PROFILE = 1,
    parameter FLIT_DATA_WIDTH = 32,
    parameter ENDPOINT_DATA_WIDTH = 128,
    parameter NUM_VCS = 4,
    parameter INPUT_VC_DEPTH = 4,
    parameter FLOW_CONTROL = 1,
    parameter ROUTING_ALGORITHM = 0,
    parameter ROUTER_OUTPUT_PIPELINE = 1,
    parameter LINK_PIPELINE_STAGES = 0,
    parameter CREDIT_RETURN_PIPELINE_STAGES = 0,
    parameter NUM_TRAFFIC_CLASSES = 8,
    parameter ENABLE_QOS = 1,
    parameter HIGH_SERVICE_BURST_LIMIT = 8,
    parameter MAX_PACKET_FLITS = 16,
    parameter NUM_TX_CHANNELS_PER_ENDPOINT = 4,
    parameter NUM_RX_CHANNELS_PER_ENDPOINT = 4,
    parameter ENDPOINT_TX_QUEUE_DEPTH = 2,
    parameter ENDPOINT_RX_VC_DEPTH = 4,
    parameter ENDPOINT_RX_QUEUE_DEPTH = 2,
    parameter MAX_ACTIVE_FLOWS = 16,
    parameter FLOW_ID_WIDTH = 16,
    parameter OWNER_ID_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
    parameter PACKAGE_ID_WIDTH = 32,
    parameter NODE_ID_WIDTH = 8,
    parameter ENDPOINT_ID_WIDTH = 8,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter MESSAGE_TYPE_WIDTH = 4,
    parameter PACKET_ID_WIDTH = 16,
    parameter FRAGMENT_INDEX_WIDTH = 4,
    parameter USER_METADATA_WIDTH = 64,
    parameter ERROR_WIDTH = 8,
    parameter LINK_EPOCH_WIDTH = 4,
    parameter EXECUTION_EPOCH_WIDTH = 8,
    parameter ALLOCATION_GENERATION_WIDTH = 16,
    parameter PACKAGE_SLOT_WIDTH = 8,
    parameter FLOW_SEQUENCE_WIDTH = 16,
    parameter FENCE_ID_WIDTH = 8,
    parameter CONFIG_DATA_WIDTH = 64,
    parameter CONFIG_VERSION_WIDTH = 16,
    parameter CONFIG_TAG_WIDTH = 16,
    parameter CONFIG_CRC_WIDTH = 32,
    parameter RUNTIME_TAG_WIDTH = 16,
    parameter DRAIN_TIMEOUT_CYCLES = 65535,
    parameter ENABLE_LINK_PARITY = 0,
    parameter BUFFER_PROTECTION = 0,
    parameter CONTROL_PROTECTION = 0,
    parameter ENABLE_FAULT_MASKS = 1,
    parameter ENABLE_COUNTERS = 1,
    parameter ENABLE_TRACE = 0,
    parameter ASYNC_ENDPOINT_MASK = 0,
    parameter ASYNC_RESET = 0,
    localparam int VW = NUM_VCS > 1 ? $clog2(NUM_VCS) : 1,
    parameter [8*VW-1:0] TRAFFIC_CLASS_TO_VC = default_vc_map(),
    parameter [7:0] TRAFFIC_CLASS_TO_SERVICE = 8'h30,
    localparam bit GEOMETRY_VALID =
        ((NOC_X > 0) === 1'b1) && (^NOC_X !== 1'bx) &&
        ((NOC_Y > 0) === 1'b1) && (^NOC_Y !== 1'bx) &&
        ((FLIT_DATA_WIDTH > 0) === 1'b1) && (^FLIT_DATA_WIDTH !== 1'bx) &&
        ((ENDPOINT_DATA_WIDTH > 0) === 1'b1) && (^ENDPOINT_DATA_WIDTH !== 1'bx) &&
        ((NUM_VCS > 0) === 1'b1) && (^NUM_VCS !== 1'bx) &&
        ((INPUT_VC_DEPTH > 0) === 1'b1) && (^INPUT_VC_DEPTH !== 1'bx) &&
        ((NUM_TX_CHANNELS_PER_ENDPOINT > 0) === 1'b1) && (^NUM_TX_CHANNELS_PER_ENDPOINT !== 1'bx) &&
        ((NUM_RX_CHANNELS_PER_ENDPOINT > 0) === 1'b1) && (^NUM_RX_CHANNELS_PER_ENDPOINT !== 1'bx) &&
        ((ENDPOINT_TX_QUEUE_DEPTH > 0) === 1'b1) && (^ENDPOINT_TX_QUEUE_DEPTH !== 1'bx) &&
        ((ENDPOINT_RX_VC_DEPTH > 0) === 1'b1) && (^ENDPOINT_RX_VC_DEPTH !== 1'bx) &&
        ((ENDPOINT_RX_QUEUE_DEPTH > 0) === 1'b1) && (^ENDPOINT_RX_QUEUE_DEPTH !== 1'bx) &&
        ((MAX_ACTIVE_FLOWS > 0) === 1'b1) && (^MAX_ACTIVE_FLOWS !== 1'bx) &&
        ((MAX_PACKET_FLITS > 0) === 1'b1) && (^MAX_PACKET_FLITS !== 1'bx) &&
        ((FRAGMENT_INDEX_WIDTH > 0) === 1'b1) && (^FRAGMENT_INDEX_WIDTH !== 1'bx) &&
        ((LINK_EPOCH_WIDTH > 0) === 1'b1) && (^LINK_EPOCH_WIDTH !== 1'bx) &&
        ((64'(DRAIN_TIMEOUT_CYCLES) <= 64'hffffffff) === 1'b1) &&
        ((DRAIN_TIMEOUT_CYCLES > 0) === 1'b1) && (^DRAIN_TIMEOUT_CYCLES !== 1'bx) &&
        ((HIGH_SERVICE_BURST_LIMIT > 0) === 1'b1) && (^HIGH_SERVICE_BURST_LIMIT !== 1'bx) &&
        ((NOC_X <= 8 && NOC_Y <= 8) === 1'b1) &&
        ((NUM_ROUTERS == NOC_X * NOC_Y) === 1'b1) &&
        ((NUM_ENDPOINTS == NUM_ROUTERS) === 1'b1) &&
        ((MAX_ACTIVE_FLOWS <= 64) === 1'b1) &&
        ((NUM_VCS <= 4) === 1'b1) &&
        ((FLIT_DATA_WIDTH % 8 == 0 && ENDPOINT_DATA_WIDTH % 8 == 0) === 1'b1) &&
        ((ENDPOINT_RX_VC_DEPTH == INPUT_VC_DEPTH) === 1'b1) &&
        ((NUM_TX_CHANNELS_PER_ENDPOINT <= 16) === 1'b1) &&
        ((NUM_RX_CHANNELS_PER_ENDPOINT <= 16) === 1'b1) &&
        ((ROUTER_OUTPUT_PIPELINE == 1) === 1'b1) &&
        ((LINK_PIPELINE_STAGES >= 0 && LINK_PIPELINE_STAGES <= 4) === 1'b1) &&
        ((CREDIT_RETURN_PIPELINE_STAGES >= 0 && CREDIT_RETURN_PIPELINE_STAGES <= 4) === 1'b1) &&
        ((FLOW_CONTROL == 0 || FLOW_CONTROL == 1) === 1'b1) &&
        ((ROUTING_ALGORITHM == 0 || ROUTING_ALGORITHM == 1) === 1'b1) &&
        ((NOC_PROFILE >= 0 && NOC_PROFILE <= 2) === 1'b1) &&
        ((ENABLE_QOS == 0 || ENABLE_QOS == 1) === 1'b1) &&
        ((ENABLE_LINK_PARITY == 0 || ENABLE_LINK_PARITY == 1) === 1'b1) &&
        ((BUFFER_PROTECTION >= 0 && BUFFER_PROTECTION <= 2) === 1'b1) &&
        ((ENABLE_FAULT_MASKS == 0 || ENABLE_FAULT_MASKS == 1) === 1'b1) &&
        ((ENABLE_COUNTERS == 0 || ENABLE_COUNTERS == 1) === 1'b1) &&
        ((ASYNC_ENDPOINT_MASK == 0 && ASYNC_RESET == 0 &&
            CONTROL_PROTECTION == 0 && ENABLE_TRACE == 0) === 1'b1) &&
        ((NOC_PROFILE != 0 || (NUM_VCS <= 2 && FLOW_CONTROL == 0 && ENABLE_QOS == 0)) === 1'b1) &&
        ((NUM_TRAFFIC_CLASSES == 8) === 1'b1) &&
        ((NOC_PROFILE == 0 || (NUM_TX_CHANNELS_PER_ENDPOINT >= 2 &&
            NUM_RX_CHANNELS_PER_ENDPOINT >= 2)) === 1'b1) &&
        ((NOC_PROFILE == 0 || FLOW_CONTROL == 1) === 1'b1) &&
        ((FLOW_CONTROL == 0 || (ENDPOINT_DATA_WIDTH + FLIT_DATA_WIDTH - 1) /
            FLIT_DATA_WIDTH <= INPUT_VC_DEPTH) === 1'b1) &&
        ((NOC_PROFILE == 0 || NUM_VCS >= 4) === 1'b1) &&
        ((NOC_PROFILE != 2 || (ENABLE_LINK_PARITY == 1 && BUFFER_PROTECTION > 0)) === 1'b1) &&
        ((FLOW_CONTROL == 0 || LINK_EPOCH_WIDTH >= 2) === 1'b1) &&
        ((FRAGMENT_INDEX_WIDTH <= 16) === 1'b1) &&
        (((ENDPOINT_DATA_WIDTH + FLIT_DATA_WIDTH - 1) /
            FLIT_DATA_WIDTH <= MAX_PACKET_FLITS) === 1'b1) &&
        ((128'(MAX_PACKET_FLITS) <= (128'd1 << FRAGMENT_INDEX_WIDTH)) === 1'b1) &&
        ((FLOW_ID_WIDTH == 16) === 1'b1) &&
        ((OWNER_ID_WIDTH == 16) === 1'b1) &&
        ((KERNEL_ID_WIDTH == 16) === 1'b1) &&
        ((PACKAGE_ID_WIDTH == 32) === 1'b1) &&
        ((NODE_ID_WIDTH == 8) === 1'b1) &&
        ((ENDPOINT_ID_WIDTH == 8) === 1'b1) &&
        ((CONTEXT_ID_WIDTH == 8) === 1'b1) &&
        ((MESSAGE_TYPE_WIDTH == 4) === 1'b1) &&
        ((PACKET_ID_WIDTH == 16) === 1'b1) &&
        ((USER_METADATA_WIDTH == 64) === 1'b1) &&
        ((ERROR_WIDTH == 8) === 1'b1) &&
        ((EXECUTION_EPOCH_WIDTH == 8) === 1'b1) &&
        ((ALLOCATION_GENERATION_WIDTH == 16) === 1'b1) &&
        ((PACKAGE_SLOT_WIDTH == 8) === 1'b1) &&
        ((FLOW_SEQUENCE_WIDTH == 16) === 1'b1) &&
        ((FENCE_ID_WIDTH == 8) === 1'b1) &&
        ((CONFIG_DATA_WIDTH == 64) === 1'b1) &&
        ((CONFIG_VERSION_WIDTH == 16) === 1'b1) &&
        ((CONFIG_TAG_WIDTH == 16) === 1'b1) &&
        ((CONFIG_CRC_WIDTH == 32) === 1'b1) &&
        ((RUNTIME_TAG_WIDTH == 16) === 1'b1),
    localparam int NN = GEOMETRY_VALID ? NUM_ROUTERS : 1,
    localparam int NE = GEOMETRY_VALID ? NUM_ENDPOINTS : 1,
    localparam int D = GEOMETRY_VALID ? FLIT_DATA_WIDTH : 1,
    localparam int TD = GEOMETRY_VALID ? ENDPOINT_DATA_WIDTH : 1,
    localparam int V = GEOMETRY_VALID ? NUM_VCS : 1,
    localparam int DEPTH = GEOMETRY_VALID ? INPUT_VC_DEPTH : 1,
    localparam int TX = GEOMETRY_VALID ? NUM_TX_CHANNELS_PER_ENDPOINT : 1,
    localparam int RX = GEOMETRY_VALID ? NUM_RX_CHANNELS_PER_ENDPOINT : 1,
    localparam int MF = GEOMETRY_VALID ? MAX_ACTIVE_FLOWS : 1,
    localparam int N = GEOMETRY_VALID ? NODE_ID_WIDTH : 1,
    localparam int EP = GEOMETRY_VALID ? ENDPOINT_ID_WIDTH : 1,
    localparam int CX = GEOMETRY_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int MT = GEOMETRY_VALID ? MESSAGE_TYPE_WIDTH : 1,
    localparam int PI = GEOMETRY_VALID ? PACKET_ID_WIDTH : 1,
    localparam int F = GEOMETRY_VALID ? FRAGMENT_INDEX_WIDTH : 1,
    localparam int U = GEOMETRY_VALID ? USER_METADATA_WIDTH : 1,
    localparam int ER = GEOMETRY_VALID ? ERROR_WIDTH : 1,
    localparam int E = GEOMETRY_VALID ? LINK_EPOCH_WIDTH : 1,
    localparam int RT = GEOMETRY_VALID ? RUNTIME_TAG_WIDTH : 1,
    localparam int K = GEOMETRY_VALID ? D / 8 : 1,
    localparam int TB = GEOMETRY_VALID ? TD / 8 : 1,
    localparam int TC = 3,
    localparam int OCC = $clog2(DEPTH + 1),
    localparam int CW = OCC,
    localparam int TO = GEOMETRY_VALID ? $clog2(ENDPOINT_TX_QUEUE_DEPTH + 1) : 1,
    localparam int VO = OCC,
    localparam int RO = GEOMETRY_VALID ? $clog2(ENDPOINT_RX_QUEUE_DEPTH + 1) : 1,
    localparam int FRAGMENTS = GEOMETRY_VALID ? (TD + D - 1) / D : 1,
    localparam int NF = FRAGMENTS > 1 ? $clog2(FRAGMENTS) : 1,
    localparam int WORDS = 2 + NN + 4 * MF,
    localparam int LW = D + K + 3 + F + VW + 2 * N + 2 * EP + CX + MT + TC + PI + U + ER + E + 1
) (
    input wire i_noc_clk,
    input wire i_noc_rstb,
    input wire i_run,
    input wire i_error_clear,
    input wire [NE-1:0] i_endpoint_clk,
    input wire [NE-1:0] i_endpoint_rstb,
    input wire i_drain_valid,
    output wire o_drain_ready,
    input wire [RT-1:0] i_drain_tag,
    input wire i_flush_valid,
    output wire o_flush_ready,
    input wire [RT-1:0] i_flush_tag,
    input wire i_drain_all,
    input wire [MF-1:0] i_drain_flow_mask,
    output wire o_lifecycle_valid,
    input wire i_lifecycle_ready,
    output wire [RT-1:0] o_lifecycle_tag,
    output wire [3-1:0] o_lifecycle_status,
    input wire i_cfg_valid,
    output wire o_cfg_ready,
    input wire [3-1:0] i_cfg_command,
    input wire [16-1:0] i_cfg_owner_id,
    input wire [16-1:0] i_cfg_kernel_id,
    input wire [32-1:0] i_cfg_package_id,
    input wire [16-1:0] i_cfg_expected_version,
    input wire [16-1:0] i_cfg_word_index,
    input wire [64-1:0] i_cfg_write_data,
    input wire [8-1:0] i_cfg_write_strobe,
    input wire [32-1:0] i_cfg_expected_crc,
    input wire [16-1:0] i_cfg_tag,
    output wire o_cfg_response_valid,
    input wire i_cfg_response_ready,
    output wire [4-1:0] o_cfg_response_status,
    output wire [64-1:0] o_cfg_response_data,
    output wire [16-1:0] o_cfg_response_version,
    output wire [32-1:0] o_cfg_response_crc,
    output wire [16-1:0] o_cfg_response_tag,
    input wire [NE*TX-1:0] i_tile_tx_valid,
    output wire [NE*TX-1:0] o_tile_tx_ready,
    input wire [NE*TX*TD-1:0] i_tile_tx_data,
    input wire [NE*TX*TB-1:0] i_tile_tx_keep,
    input wire [NE*TX-1:0] i_tile_tx_last,
    input wire [NE*TX*CX-1:0] i_tile_tx_context_id,
    input wire [NE*TX*MT-1:0] i_tile_tx_message_type,
    input wire [NE*TX*TC-1:0] i_tile_tx_traffic_class,
    input wire [NE*TX*PI-1:0] i_tile_tx_packet_id,
    input wire [NE*TX*U-1:0] i_tile_tx_user_metadata,
    input wire [NE*TX*ER-1:0] i_tile_tx_error,
    input wire [NE*TX*N-1:0] i_tile_tx_destination_node,
    input wire [NE*TX*EP-1:0] i_tile_tx_destination_endpoint,
    output wire [NE*RX-1:0] o_tile_rx_valid,
    input wire [NE*RX-1:0] i_tile_rx_ready,
    output wire [NE*RX*TD-1:0] o_tile_rx_data,
    output wire [NE*RX*TB-1:0] o_tile_rx_keep,
    output wire [NE*RX-1:0] o_tile_rx_last,
    output wire [NE*RX*CX-1:0] o_tile_rx_context_id,
    output wire [NE*RX*MT-1:0] o_tile_rx_message_type,
    output wire [NE*RX*TC-1:0] o_tile_rx_traffic_class,
    output wire [NE*RX*PI-1:0] o_tile_rx_packet_id,
    output wire [NE*RX*U-1:0] o_tile_rx_user_metadata,
    output wire [NE*RX*ER-1:0] o_tile_rx_error,
    output wire [NE*RX*N-1:0] o_tile_rx_source_node,
    output wire [NE*RX*EP-1:0] o_tile_rx_source_endpoint,
    input wire [NE*TX-1:0] i_response_reserved,
    output wire o_configured,
    output wire o_running,
    output wire o_idle,
    output wire o_quiescent,
    output wire o_draining,
    output wire o_flushing,
    output wire [NN-1:0] o_router_idle,
    output wire [NE-1:0] o_endpoint_idle,
    output wire [NN*5-1:0] o_link_idle,
    output wire [MF-1:0] o_flow_valid,
    output wire [MF*16-1:0] o_flow_outstanding,
    output wire [NN*5*E-1:0] o_link_epoch,
    output wire [8-1:0] o_execution_epoch,
    output wire [16-1:0] o_active_version,
    output wire [32-1:0] o_active_package_id,
    output wire [NN*5*V*OCC-1:0] o_router_input_vc_occupancy,
    output wire [NN*5*V*CW-1:0] o_router_output_credit_count,
    output wire [NE*TX*TO-1:0] o_endpoint_tx_queue_occupancy,
    output wire [NE*V*VO-1:0] o_endpoint_rx_vc_occupancy,
    output wire [NE*RX*RO-1:0] o_endpoint_rx_queue_occupancy,
    output wire [NN*5-1:0] o_fault_mask,
    output wire o_error,
    output wire [8-1:0] o_error_code,
    output wire o_fatal_error,
    output wire [16-1:0] o_error_flow,
    output wire [N-1:0] o_error_endpoint,
    output wire [64-1:0] o_accepted_packets,
    output wire [64-1:0] o_delivered_packets,
    output wire [64-1:0] o_discarded_packets,
    output wire [8*32-1:0] o_class_packets,
    output wire [MF*32-1:0] o_flow_packets
);
    import global_noc_pkg::*;

    function automatic logic [8*VW-1:0] default_vc_map();
        logic [8*VW-1:0] result;
        result = '0;

        if (NOC_PROFILE != 0) begin
            result[2*VW+:VW] = VW'(1);
            result[3*VW+:VW] = VW'(2);
            result[4*VW+:VW] = VW'(3);
            result[5*VW+:VW] = VW'(3);
        end

        return result;

    endfunction
    function automatic bit maps_valid();
        bit legal;
        legal = (^TRAFFIC_CLASS_TO_VC !== 1'bx) &&
            (^TRAFFIC_CLASS_TO_SERVICE !== 1'bx);

        for (int c = 0; c < 8; c++)
            if (32'(TRAFFIC_CLASS_TO_VC[c*VW+:VW]) >= NUM_VCS) legal = 1'b0;

        if (NOC_PROFILE != 0) legal = legal && TRAFFIC_CLASS_TO_VC == default_vc_map() &&
            TRAFFIC_CLASS_TO_SERVICE == 8'h30;

        return legal;
    endfunction

    function automatic logic [63:0] layout_signature();
        logic [63:0] value;
        value = 64'h474e4f4300000001;
        value = {value[56:0], value[63:57]} ^ 64'(NOC_X);
        value = {value[56:0], value[63:57]} ^ 64'(NOC_Y);
        value = {value[56:0], value[63:57]} ^ 64'(NUM_ROUTERS);
        value = {value[56:0], value[63:57]} ^ 64'(NUM_ENDPOINTS);
        value = {value[56:0], value[63:57]} ^ 64'(NOC_PROFILE);
        value = {value[56:0], value[63:57]} ^ 64'(FLIT_DATA_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(ENDPOINT_DATA_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(NUM_VCS);
        value = {value[56:0], value[63:57]} ^ 64'(INPUT_VC_DEPTH);
        value = {value[56:0], value[63:57]} ^ 64'(FLOW_CONTROL);
        value = {value[56:0], value[63:57]} ^ 64'(ROUTING_ALGORITHM);
        value = {value[56:0], value[63:57]} ^ 64'(ROUTER_OUTPUT_PIPELINE);
        value = {value[56:0], value[63:57]} ^ 64'(LINK_PIPELINE_STAGES);
        value = {value[56:0], value[63:57]} ^ 64'(CREDIT_RETURN_PIPELINE_STAGES);
        value = {value[56:0], value[63:57]} ^ 64'(NUM_TRAFFIC_CLASSES);
        value = {value[56:0], value[63:57]} ^ 64'(ENABLE_QOS);
        value = {value[56:0], value[63:57]} ^ 64'(HIGH_SERVICE_BURST_LIMIT);
        value = {value[56:0], value[63:57]} ^ 64'(MAX_PACKET_FLITS);
        value = {value[56:0], value[63:57]} ^ 64'(NUM_TX_CHANNELS_PER_ENDPOINT);
        value = {value[56:0], value[63:57]} ^ 64'(NUM_RX_CHANNELS_PER_ENDPOINT);
        value = {value[56:0], value[63:57]} ^ 64'(ENDPOINT_TX_QUEUE_DEPTH);
        value = {value[56:0], value[63:57]} ^ 64'(ENDPOINT_RX_VC_DEPTH);
        value = {value[56:0], value[63:57]} ^ 64'(ENDPOINT_RX_QUEUE_DEPTH);
        value = {value[56:0], value[63:57]} ^ 64'(MAX_ACTIVE_FLOWS);
        value = {value[56:0], value[63:57]} ^ 64'(FLOW_ID_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(OWNER_ID_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(KERNEL_ID_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(PACKAGE_ID_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(NODE_ID_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(ENDPOINT_ID_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(CONTEXT_ID_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(MESSAGE_TYPE_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(PACKET_ID_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(FRAGMENT_INDEX_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(USER_METADATA_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(ERROR_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(LINK_EPOCH_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(EXECUTION_EPOCH_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(ALLOCATION_GENERATION_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(PACKAGE_SLOT_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(FLOW_SEQUENCE_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(FENCE_ID_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(CONFIG_DATA_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(CONFIG_VERSION_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(CONFIG_TAG_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(CONFIG_CRC_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(RUNTIME_TAG_WIDTH);
        value = {value[56:0], value[63:57]} ^ 64'(DRAIN_TIMEOUT_CYCLES);
        value = {value[56:0], value[63:57]} ^ 64'(ENABLE_LINK_PARITY);
        value = {value[56:0], value[63:57]} ^ 64'(BUFFER_PROTECTION);
        value = {value[56:0], value[63:57]} ^ 64'(CONTROL_PROTECTION);
        value = {value[56:0], value[63:57]} ^ 64'(ENABLE_FAULT_MASKS);
        value = {value[56:0], value[63:57]} ^ 64'(ENABLE_COUNTERS);
        value = {value[56:0], value[63:57]} ^ 64'(ENABLE_TRACE);
        value = {value[56:0], value[63:57]} ^ 64'(ASYNC_ENDPOINT_MASK);
        value = {value[56:0], value[63:57]} ^ 64'(ASYNC_RESET);
        value = {value[56:0], value[63:57]} ^ 64'(TRAFFIC_CLASS_TO_VC);
        value = {value[56:0], value[63:57]} ^ 64'(TRAFFIC_CLASS_TO_SERVICE);

        return value;
    endfunction

    if (!GEOMETRY_VALID || !maps_valid()) begin : g_invalid_parameters
        global_noc_parameters_must_be_valid invalid_parameters ();
    end else begin : g_noc
        localparam logic [63:0] SIGNATURE = layout_signature();
        wire [5*D-1:0] r_in_data[NN];
        wire [5*D-1:0] r_out_data[NN];
        wire [D-1:0] t_tx_data[NE];
        wire [D-1:0] t_rx_data[NE];
        wire [5*K-1:0] r_in_keep[NN];
        wire [5*K-1:0] r_out_keep[NN];
        wire [K-1:0] t_tx_keep[NE];
        wire [K-1:0] t_rx_keep[NE];
        wire [4:0] r_in_head[NN];
        wire [4:0] r_out_head[NN];
        wire t_tx_head[NE];
        wire t_rx_head[NE];
        wire [4:0] r_in_tail[NN];
        wire [4:0] r_out_tail[NN];
        wire t_tx_tail[NE];
        wire t_rx_tail[NE];
        wire [5*F-1:0] r_in_fragment_index[NN];
        wire [5*F-1:0] r_out_fragment_index[NN];
        wire [NF-1:0] t_tx_fragment_index[NE];
        wire [NF-1:0] t_rx_fragment_index[NE];
        wire [5*VW-1:0] r_in_vc[NN];
        wire [5*VW-1:0] r_out_vc[NN];
        wire [VW-1:0] t_tx_vc[NE];
        wire [VW-1:0] t_rx_vc[NE];
        wire [5*N-1:0] r_in_source_node[NN];
        wire [5*N-1:0] r_out_source_node[NN];
        wire [N-1:0] t_tx_source_node[NE];
        wire [N-1:0] t_rx_source_node[NE];
        wire [5*EP-1:0] r_in_source_endpoint[NN];
        wire [5*EP-1:0] r_out_source_endpoint[NN];
        wire [EP-1:0] t_tx_source_endpoint[NE];
        wire [EP-1:0] t_rx_source_endpoint[NE];
        wire [5*N-1:0] r_in_destination_node[NN];
        wire [5*N-1:0] r_out_destination_node[NN];
        wire [N-1:0] t_tx_destination_node[NE];
        wire [N-1:0] t_rx_destination_node[NE];
        wire [5*EP-1:0] r_in_destination_endpoint[NN];
        wire [5*EP-1:0] r_out_destination_endpoint[NN];
        wire [EP-1:0] t_tx_destination_endpoint[NE];
        wire [EP-1:0] t_rx_destination_endpoint[NE];
        wire [5*CX-1:0] r_in_context_id[NN];
        wire [5*CX-1:0] r_out_context_id[NN];
        wire [CX-1:0] t_tx_context_id[NE];
        wire [CX-1:0] t_rx_context_id[NE];
        wire [5*MT-1:0] r_in_message_type[NN];
        wire [5*MT-1:0] r_out_message_type[NN];
        wire [MT-1:0] t_tx_message_type[NE];
        wire [MT-1:0] t_rx_message_type[NE];
        wire [5*TC-1:0] r_in_traffic_class[NN];
        wire [5*TC-1:0] r_out_traffic_class[NN];
        wire [TC-1:0] t_tx_traffic_class[NE];
        wire [TC-1:0] t_rx_traffic_class[NE];
        wire [5*PI-1:0] r_in_packet_id[NN];
        wire [5*PI-1:0] r_out_packet_id[NN];
        wire [PI-1:0] t_tx_packet_id[NE];
        wire [PI-1:0] t_rx_packet_id[NE];
        wire [4:0] r_in_stream_last[NN];
        wire [4:0] r_out_stream_last[NN];
        wire t_tx_stream_last[NE];
        wire t_rx_stream_last[NE];
        wire [5*U-1:0] r_in_user_metadata[NN];
        wire [5*U-1:0] r_out_user_metadata[NN];
        wire [U-1:0] t_tx_user_metadata[NE];
        wire [U-1:0] t_rx_user_metadata[NE];
        wire [5*ER-1:0] r_in_error[NN];
        wire [5*ER-1:0] r_out_error[NN];
        wire [ER-1:0] t_tx_error[NE];
        wire [ER-1:0] t_rx_error[NE];
        wire [5*E-1:0] r_in_epoch[NN];
        wire [5*E-1:0] r_out_epoch[NN];
        wire [E-1:0] t_tx_epoch[NE];
        wire [E-1:0] t_rx_epoch[NE];
        wire [4:0] r_in_parity[NN];
        wire [4:0] r_out_parity[NN];
        wire t_tx_parity[NE];
        wire t_rx_parity[NE];
        wire [4:0] r_in_valid[NN];
        wire [4:0] r_in_ready[NN];
        wire [4:0] r_out_valid[NN];
        wire [4:0] r_out_ready[NN];
        wire [4:0] r_return_valid[NN];
        wire [4:0] r_credit_valid[NN];
        wire [5*VW-1:0] r_return_vc[NN];
        wire [5*E-1:0] r_return_epoch[NN];
        wire [5*VW-1:0] r_credit_vc[NN];
        wire [5*E-1:0] r_credit_epoch[NN];
        wire [NE-1:0] t_tx_valid;
        wire [NE-1:0] t_tx_ready;
        wire [NE-1:0] t_rx_valid;
        wire [NE-1:0] t_rx_ready;
        wire [NE-1:0] t_return_valid;
        wire [NE-1:0] t_credit_valid;
        wire [VW-1:0] t_return_vc[NE];
        wire [E-1:0] t_return_epoch[NE];
        wire [VW-1:0] t_credit_vc[NE];
        wire [E-1:0] t_credit_epoch[NE];
        wire [NN-1:0] router_config_ready;
        wire [NE-1:0] endpoint_config_ready;
        wire [NN-1:0] router_idle;
        wire [NE-1:0] endpoint_idle;
        wire [NN-1:0] router_error;
        wire [NN-1:0] router_fatal;
        wire [NE-1:0] endpoint_error;
        wire [NN*5-1:0] link_busy;
        wire [NE*2-1:0] local_busy;
        wire [NE-1:0] fragment_bad;
        wire [NE*TX-1:0] native_tx_valid;
        wire [NE*TX-1:0] native_tx_ready;
        wire [NE*RX-1:0] native_rx_valid;
        wire [NE*RX-1:0] native_rx_ready;
        wire [NE*RX*TD-1:0] native_rx_data;
        assign o_tile_rx_data = native_rx_data;
        wire [NE*RX*TB-1:0] native_rx_keep;
        assign o_tile_rx_keep = native_rx_keep;
        wire [NE*RX-1:0] native_rx_last;
        assign o_tile_rx_last = native_rx_last;
        wire [NE*RX*CX-1:0] native_rx_context_id;
        assign o_tile_rx_context_id = native_rx_context_id;
        wire [NE*RX*MT-1:0] native_rx_message_type;
        assign o_tile_rx_message_type = native_rx_message_type;
        wire [NE*RX*TC-1:0] native_rx_traffic_class;
        assign o_tile_rx_traffic_class = native_rx_traffic_class;
        wire [NE*RX*PI-1:0] native_rx_packet_id;
        assign o_tile_rx_packet_id = native_rx_packet_id;
        wire [NE*RX*U-1:0] native_rx_user_metadata;
        assign o_tile_rx_user_metadata = native_rx_user_metadata;
        wire [NE*RX*ER-1:0] native_rx_error;
        assign o_tile_rx_error = native_rx_error;
        wire [NE*RX*N-1:0] native_rx_source_node;
        assign o_tile_rx_source_node = native_rx_source_node;
        wire [NE*RX*EP-1:0] native_rx_source_endpoint;
        assign o_tile_rx_source_endpoint = native_rx_source_endpoint;
        wire native_config_ready = (&router_config_ready) && (&endpoint_config_ready);
        wire native_config_valid;
        wire flush_pulse;
        wire transport_idle;
        wire transport_fault = (|router_error) || (|endpoint_error);
        wire transport_fatal = (|router_fatal) || (|fragment_bad);

        logic [63:0] candidate[WORDS];
        logic [63:0] image[WORDS];
        wire [MF*256-1:0] candidate_records;
        wire [MF*256-1:0] active_records;
        wire [NN*5-1:0] candidate_faults;
        logic configured;
        logic applying;
        logic prepared;
        logic [15:0] version;
        logic [15:0] candidate_owner;
        logic [15:0] candidate_kernel;
        logic [31:0] candidate_package;
        logic candidate_owned;
        logic [15:0] active_owner;
        logic [15:0] active_kernel;
        logic [31:0] active_package;
        logic [7:0] execution_epoch;
        logic [E-1:0] link_epoch;
        logic [MF-1:0] blocked;
        logic draining;
        logic flushing;
        logic [31:0] drain_cycles;
        logic [3:0] drain_settle;
        logic [RT-1:0] lifecycle_tag;
        logic lifecycle_valid;
        lifecycle_status_t lifecycle_status;
        logic response_valid;
        config_status_t response_status;
        logic [63:0] response_data;
        logic [31:0] response_crc;
        logic [15:0] response_tag;
        logic error_flag;
        error_t error_code;
        logic fatal;
        logic [15:0] error_flow;
        logic [N-1:0] error_endpoint;
        logic [15:0] outstanding[MF];
        logic [15:0] tx_sequence[MF][V];
        logic [15:0] rx_sequence[MF][V];
        logic [V-1:0] tx_exhausted[MF];
        logic [V-1:0] rx_exhausted[MF];
        logic [63:0] accepted_packets;
        logic [63:0] delivered_packets;
        logic [63:0] discarded_packets;
        logic [31:0] class_packets[8];
        logic [31:0] flow_packets[MF];
        logic [NE*TX-1:0] tx_legal;
        logic [NE*RX-1:0] rx_legal;
        logic [NE*TX-1:0] tx_binding;
        logic [NE*TX-1:0] tx_sequence_legal;
        integer tx_flow[NE*TX];
        integer rx_flow[NE*RX];
        integer tx_vc[NE*TX];
        integer rx_vc[NE*RX];
        logic [31:0] candidate_crc;
        logic candidate_valid;
        logic selected_empty;
        wire enabled = (i_noc_rstb === 1'b1) && configured &&
            (i_run === 1'b1) &&!fatal &&!transport_fatal &&!applying &&!flushing &&!flush_pulse;
        wire configure_fire = i_cfg_valid === 1'b1 && o_cfg_ready;
        wire drain_fire = i_drain_valid === 1'b1 && o_drain_ready;
        wire flush_fire = i_flush_valid === 1'b1 && o_flush_ready;
        wire [NE*TX-1:0] tx_fire = i_tile_tx_valid & o_tile_tx_ready;
        wire [NE*RX-1:0] rx_fire = o_tile_rx_valid & i_tile_rx_ready;

        assign o_configured = configured;
        assign o_running = enabled && blocked != {MF{1'b1}};
        assign o_draining = draining;
        assign o_flushing = flushing;
        assign o_execution_epoch = execution_epoch;
        assign o_active_version = version;
        assign o_active_package_id = active_package;
        assign o_error = error_flag || transport_fault;
        assign o_error_code = error_code != NOC_ERROR_NONE ? error_code :
            transport_fault ? NOC_ERROR_TRANSPORT : NOC_ERROR_NONE;
        assign o_error_flow = error_flow;
        assign o_error_endpoint = error_endpoint;
        assign o_fatal_error = fatal || transport_fatal;
        assign o_accepted_packets = accepted_packets;
        assign o_delivered_packets = delivered_packets;
        assign o_discarded_packets = discarded_packets;
        assign o_lifecycle_valid = lifecycle_valid;
        assign o_lifecycle_tag = lifecycle_tag;
        assign o_lifecycle_status = lifecycle_status;
        assign o_cfg_response_valid = response_valid;
        assign o_cfg_response_status = response_status;
        assign o_cfg_response_data = response_data;
        assign o_cfg_response_version = version;
        assign o_cfg_response_crc = response_crc;
        assign o_cfg_response_tag = response_tag;
        assign o_router_idle = router_idle;
        assign o_endpoint_idle = endpoint_idle;
        assign o_link_idle = ~link_busy;
        assign transport_idle = (&router_idle) && (&endpoint_idle) &&!(|link_busy) &&
            !(|local_busy);
        assign o_idle = transport_idle && o_flow_outstanding == '0;
        assign o_quiescent = o_idle &&!i_cfg_valid &&!i_drain_valid &&!i_flush_valid &&
            !i_error_clear &&!(|i_tile_tx_valid) &&!draining &&!flushing &&!applying;
        assign o_cfg_ready = !response_valid &&!applying &&!draining &&!flushing &&
            !lifecycle_valid &&!i_drain_valid &&!i_flush_valid;
        assign o_flush_ready = !flushing &&!draining &&!applying &&!response_valid &&
            !lifecycle_valid &&!i_cfg_valid;
        assign o_drain_ready = !draining &&!flushing &&!applying &&!response_valid &&
            !lifecycle_valid &&!i_cfg_valid &&!i_flush_valid;
        assign native_config_valid = applying && native_config_ready;
        assign flush_pulse = flushing;
        assign native_tx_valid = i_tile_tx_valid & tx_legal;
        assign o_tile_tx_ready = native_tx_ready & tx_legal;
        assign o_tile_rx_valid = native_rx_valid & rx_legal;
        assign native_rx_ready = i_tile_rx_ready & rx_legal;

        for (genvar f = 0; f < MF; f++) begin : g_flow_table
            localparam int BASE = 2 + NN + 4 * f;
            assign candidate_records[f*256+:256] = {candidate[BASE+3], candidate[BASE+2],
                candidate[BASE+1], candidate[BASE]};
            assign active_records[f*256+:256] = {image[BASE+3], image[BASE+2],
                image[BASE+1], image[BASE]};
            assign o_flow_valid[f] = configured && image[BASE][0];
            assign o_flow_outstanding[f*16+:16] = outstanding[f];
            assign o_flow_packets[f*32+:32] = flow_packets[f];
        end

        for (genvar n = 0; n < NN; n++) begin : g_fault_table
            assign candidate_faults[n*5+:5] = candidate[2+n][4:0];
            assign o_fault_mask[n*5+:5] = image[2+n][4:0];
        end

        for (genvar c = 0; c < 8; c++) begin : g_class_counters
            assign o_class_packets[c*32+:32] = class_packets[c];
        end

        function automatic logic [4:0] present_ports(input int n);
            logic [4:0] mask;
            mask = 5'b00001;
            mask[1] = n / NOC_X > 0;
            mask[2] = n % NOC_X < NOC_X - 1;
            mask[3] = n / NOC_X < NOC_Y - 1;
            mask[4] = n % NOC_X > 0;

            return mask;
        endfunction

        function automatic bit reachable(input int src, input int dst);
            int current_node;
            int next_node;
            int direction;
            int reverse_port;
            bit legal;
            current_node = src;
            legal = src < NN && dst < NN;

            if (legal) legal = !candidate_faults[src*5] &&!candidate_faults[dst*5];

            for (int hop = 0; hop < NOC_X + NOC_Y; hop++) begin
                if (legal && current_node != dst) begin
                    if ((ROUTING_ALGORITHM == 0 && current_node % NOC_X != dst % NOC_X) ||
                        current_node / NOC_X == dst / NOC_X) begin
                        direction = current_node % NOC_X < dst % NOC_X ? 2 : 4;
                        next_node = direction == 2 ? current_node + 1 : current_node - 1;
                        reverse_port = direction == 2 ? 4 : 2;
                    end else begin
                        direction = current_node / NOC_X < dst / NOC_X ? 3 : 1;
                        next_node = direction == 3 ? current_node + NOC_X : current_node - NOC_X;
                        reverse_port = direction == 3 ? 1 : 3;
                    end

                    legal = !candidate_faults[current_node*5+direction] &&
                        !candidate_faults[next_node*5+reverse_port];
                    current_node = next_node;
                end
            end

            return legal && current_node == dst;
        endfunction

        // CRC32C covers every image byte in increasing word/little-endian order.
        // Validation is on the dedicated slow control path, never the flit path.
        always @* begin : p_validate
            flow_t f;
            flow_t other;
            logic [31:0] crc;
            logic reply_found;
            crc = '1;

            for (int w = 0; w < WORDS; w++) begin
                for (int b = 0; b < 64; b++) begin
                    // Preserve the existing procedural branch for X/Z feedback.
                    crc = crc_pkg::crc32c_step(crc, (crc[0] ^ candidate[w][b]) === 1'b1);
                end
            end

            candidate_crc = ~crc;
            candidate_valid = candidate[0] == SIGNATURE &&
                candidate[1] == 64'h4e4f430000000001 && candidate_owned;

            if (^{candidate_owner, candidate_kernel, candidate_package} === 1'bx)
                candidate_valid = 1'b0;

            for (int w = 0; w < WORDS; w++)
                if (^candidate[w] === 1'bx) candidate_valid = 1'b0;

            for (int n = 0; n < NN; n++) begin
                if ((candidate[2+n] & ~64'(present_ports(n))) != 0)
                    candidate_valid = 1'b0;

                if (!ENABLE_FAULT_MASKS && candidate[2+n] != 0) candidate_valid = 1'b0;
            end

            for (int i = 0; i < MF; i++) begin
                f = decode_flow(candidate_records[i*256+:256]);

                if (f.valid) begin
                    if (f.source_node >= NE || f.destination_node >= NE ||
                        f.source_channel >= TX || f.destination_channel >= RX || f.budget == 0 ||
                        f.classes == 0 || f.messages == 0 || f.epoch != execution_epoch ||
                        f.package_id != candidate_package ||!reachable(f.source_node,
                        f.destination_node) || candidate[2+NN+i*4][63:57] != 0 ||
                        candidate[5+NN+i*4][63:32] != 0) candidate_valid = 1'b0;

                    if (NOC_PROFILE == 0 && (f.classes & 8'h3c) != 0)
                        candidate_valid = 1'b0;

                    // Dedicated critical ejection prevents data backpressure from
                    // occupying the endpoint's reserved event/runtime queue.
                    if ((f.classes & 8'h30) != 0 && (RX < 2 || TX < 2 ||
                        f.destination_channel != RX - 1 || f.source_channel != TX - 1 ||
                        (f.classes & 8'hcf) != 0))
                        candidate_valid = 1'b0;

                    if (NOC_PROFILE != 0 && (f.classes & 8'hcf) != 0 &&
                        (f.destination_channel == RX - 1 || f.source_channel == TX - 1))
                        candidate_valid = 1'b0;

                    reply_found = !f.classes[NOC_REQUEST];

                    for (int j = 0; j < MF; j++) begin
                        other = decode_flow(candidate_records[j*256+:256]);

                        if (j != i && other.valid && other.id == f.id)
                            candidate_valid = 1'b0;

                        if (other.valid && other.id == f.reply_flow &&
                            other.classes[NOC_RESPONSE] &&
                            other.source_node == f.destination_node &&
                            other.destination_node == f.source_node && other.owner == f.owner &&
                            other.kernel == f.kernel && other.package_id == f.package_id)
                            reply_found = 1'b1;
                    end

                    if (!reply_found) candidate_valid = 1'b0;
                end
            end
        end

        function automatic bit known_tx(input int c);
            bit legal;
            legal = (^{i_tile_tx_keep[c*TB+:TB], i_tile_tx_last[c],
                i_tile_tx_context_id[c*CX+:CX], i_tile_tx_message_type[c*MT+:MT],
                i_tile_tx_traffic_class[c*TC+:TC], i_tile_tx_packet_id[c*PI+:PI],
                i_tile_tx_user_metadata[c*U+:U], i_tile_tx_error[c*ER+:ER],
                i_tile_tx_destination_node[c*N+:N],
                i_tile_tx_destination_endpoint[c*EP+:EP]} !== 1'bx) &&
                i_tile_tx_keep[c*TB+:TB] != 0;

            for (int b = 0; b < TB; b++)
                if (i_tile_tx_keep[c*TB+b] && ^i_tile_tx_data[c*TD+b*8+:8] === 1'bx)
                    legal = 1'b0;

            return legal;
        endfunction

        // Only a matching, nonexhausted binding can reach native TNI admission.
        // One flow owns one source channel/destination tuple; native per-channel
        // FIFO ordering plus a fixed VC route preserves the declared flow order.
        always_comb begin : p_admission
            flow_t f;
            logic [63:0] meta;
            int traffic_class;
            int message_type;
            tx_legal = '0;
            rx_legal = '0;
            tx_binding = '0;
            tx_sequence_legal = '0;
            selected_empty = 1'b1;

            for (int fidx = 0; fidx < MF; fidx++)
                if (blocked[fidx] && outstanding[fidx] != 0) selected_empty = 1'b0;

            for (int c = 0; c < NE * TX; c++) begin
                tx_flow[c] = -1;
                meta = i_tile_tx_user_metadata[c*U+:U];
                traffic_class = int'(i_tile_tx_traffic_class[c*TC+:TC]);
                message_type = int'(i_tile_tx_message_type[c*MT+:MT]);
                tx_vc[c] = int'(TRAFFIC_CLASS_TO_VC[traffic_class*VW+:VW]);

                for (int k = 0; k < MF; k++) begin
                    f = decode_flow(active_records[k*256+:256]);

                    if (configured && f.valid && f.id == meta[15:0]) begin
                        tx_flow[c] = k;
                        tx_binding[c] = (known_tx(c) &&
                            f.generation == meta[31:16] && execution_epoch == meta[39:32] &&
                            f.slot == meta[47:40] && f.source_node == c / TX &&
                            f.source_channel == c % TX &&
                            f.destination_node == i_tile_tx_destination_node[c*N+:N] &&
                            f.destination_channel ==
                            i_tile_tx_destination_endpoint[c*EP+:EP] &&
                            f.context_id == i_tile_tx_context_id[c*CX+:CX] &&
                            ((f.classes >> traffic_class) & 1'b1) &&
                            ((f.messages >> message_type) & 1'b1)) === 1'b1;
                        tx_sequence_legal[c] = (!tx_exhausted[k][tx_vc[c]] &&
                            tx_sequence[k][tx_vc[c]] == meta[63:48]) === 1'b1;
                        tx_legal[c] = tx_binding[c] && tx_sequence_legal[c] &&
                            enabled &&!blocked[k] &&!drain_fire &&!flush_fire &&
                            outstanding[k] < f.budget &&
                            (traffic_class != int'(NOC_REQUEST) || i_response_reserved[c] === 1'b1);
                    end
                end
            end

            for (int c = 0; c < NE * RX; c++) begin
                rx_flow[c] = -1;
                meta = native_rx_user_metadata[c*U+:U];
                traffic_class = int'(native_rx_traffic_class[c*TC+:TC]);
                message_type = int'(native_rx_message_type[c*MT+:MT]);
                rx_vc[c] = int'(TRAFFIC_CLASS_TO_VC[traffic_class*VW+:VW]);

                for (int k = 0; k < MF; k++) begin
                    f = decode_flow(active_records[k*256+:256]);

                    if (configured && f.valid && f.id == meta[15:0]) begin
                        rx_flow[c] = k;
                        rx_legal[c] = (!flushing &&!fatal &&!transport_fatal &&
                            f.generation == meta[31:16] &&
                            execution_epoch == meta[39:32] && f.slot == meta[47:40] &&
                            f.destination_node == c / RX && f.destination_channel == c % RX &&
                            f.source_node == native_rx_source_node[c*N+:N] &&
                            f.source_channel == native_rx_source_endpoint[c*EP+:EP] &&
                            f.context_id == native_rx_context_id[c*CX+:CX] &&
                            ((f.classes >> traffic_class) & 1'b1) &&
                            ((f.messages >> message_type) & 1'b1) &&
                            outstanding[k] != 0 &&!rx_exhausted[k][rx_vc[c]] &&
                            rx_sequence[k][rx_vc[c]] == meta[63:48]) === 1'b1;
                    end
                end
            end
        end

        // Control records remain stable until acknowledged. Lifecycle commands
        // are serialized; flush wins simultaneous offers before drain acceptance.
        // An accepted drain keeps its tag until completion or timeout.
        always_ff @(posedge i_noc_clk) begin : p_control
            int accepts;
            int deliveries;
            int delta;
            int increments;
            flow_t f;

            if (i_noc_rstb === 1'b0) begin
                configured <= 1'b0;
                applying <= 1'b0;
                prepared <= 1'b0;
                candidate_owned <= 1'b0;
                candidate_owner <= '0;
                candidate_kernel <= '0;
                candidate_package <= '0;
                active_owner <= '0;
                active_kernel <= '0;
                active_package <= '0;
                execution_epoch <= '0;
                link_epoch <= '0;
                version <= '0;
                blocked <= '0;
                draining <= 1'b0;
                flushing <= 1'b0;
                drain_cycles <= '0;
                drain_settle <= '0;
                lifecycle_valid <= 1'b0;
                lifecycle_tag <= '0;
                lifecycle_status <= NOC_DRAINED;
                response_valid <= 1'b0;
                response_status <= NOC_CFG_OK;
                response_data <= '0;
                response_crc <= '0;
                response_tag <= '0;
                error_flag <= 1'b0;
                error_code <= NOC_ERROR_NONE;
                error_flow <= '0;
                error_endpoint <= '0;
                fatal <= 1'b0;
                accepted_packets <= '0;
                delivered_packets <= '0;
                discarded_packets <= '0;

                for (int w = 0; w < WORDS; w++) begin
                    candidate[w] <= '0;
                    image[w] <= '0;
                end

                for (int k = 0; k < MF; k++) begin
                    outstanding[k] <= '0;
                    tx_exhausted[k] <= '0;
                    rx_exhausted[k] <= '0;
                    flow_packets[k] <= '0;

                    for (int v = 0; v < V; v++) begin
                        tx_sequence[k][v] <= '0;
                        rx_sequence[k][v] <= '0;
                    end
                end

                for (int c = 0; c < 8; c++) class_packets[c] <= '0;
            end else if (i_noc_rstb === 1'b1) begin
                if (response_valid && i_cfg_response_ready === 1'b1) response_valid <= 1'b0;

                if (lifecycle_valid && i_lifecycle_ready === 1'b1) lifecycle_valid <= 1'b0;

                if (i_error_clear === 1'b1 &&!fatal) begin
                    error_flag <= 1'b0;
                    error_code <= NOC_ERROR_NONE;
                end

                if (!i_run &&!draining &&!flushing) blocked <= '0;

                if (transport_fatal || (|endpoint_error)) begin
                    fatal <= 1'b1;
                    error_flag <= 1'b1;
                    error_code <= NOC_ERROR_TRANSPORT;
                end

                if (applying && native_config_ready) begin
                    applying <= 1'b0;
                    configured <= 1'b1;
                    version <= version + 1'b1;
                    response_valid <= 1'b1;
                    response_status <= NOC_CFG_OK;
                end

                if (configure_fire) begin
                    response_valid <= 1'b1;
                    response_status <= NOC_CFG_OK;
                    response_tag <= i_cfg_tag;
                    response_data <= '0;
                    response_crc <= candidate_crc;

                    if (i_cfg_expected_version !== version) response_status <= NOC_CFG_VERSION;
                    else if (candidate_owned && (i_cfg_owner_id !== candidate_owner ||
                        i_cfg_kernel_id !== candidate_kernel ||
                        i_cfg_package_id !== candidate_package)) response_status <= NOC_CFG_OWNER;
                    else if (configured && (i_cfg_owner_id !== active_owner ||
                        i_cfg_kernel_id !== active_kernel)) response_status <= NOC_CFG_OWNER;
                    else begin
                        case (i_cfg_command)
                            NOC_CFG_WRITE: begin
                                if (i_cfg_word_index >= WORDS) response_status <= NOC_CFG_INDEX;
                                else begin
                                    candidate_owned <= 1'b1;
                                    candidate_owner <= i_cfg_owner_id;
                                    candidate_kernel <= i_cfg_kernel_id;
                                    candidate_package <= i_cfg_package_id;
                                    prepared <= 1'b0;

                                    for (int b = 0; b < 8; b++)
                                        if (i_cfg_write_strobe[b])
                                            candidate[i_cfg_word_index][b*8+:8] <=
                                                i_cfg_write_data[b*8+:8];
                                end
                            end
                            NOC_CFG_READ: begin
                                if (i_cfg_word_index >= WORDS) response_status <= NOC_CFG_INDEX;
                                else response_data <= candidate[i_cfg_word_index];
                            end
                            NOC_CFG_VALIDATE, NOC_CFG_PREPARE: begin
                                if (!candidate_valid) response_status <= NOC_CFG_IMAGE;
                                else if (candidate_crc !== i_cfg_expected_crc)
                                    response_status <= NOC_CFG_CRC;
                                else if (i_cfg_command == NOC_CFG_PREPARE) prepared <= 1'b1;
                            end
                            NOC_CFG_COMMIT: begin
                                if (!prepared ||!candidate_valid) response_status <= NOC_CFG_IMAGE;
                                else if (candidate_crc !== i_cfg_expected_crc)
                                    response_status <= NOC_CFG_CRC;
                                else if (!o_idle || i_run || version == 16'hffff || fatal)
                                    response_status <= NOC_CFG_BUSY;
                                else begin
                                    for (int w = 0; w < WORDS; w++) image[w] <= candidate[w];

                                    for (int k = 0; k < MF; k++) begin
                                        f = decode_flow(candidate_records[k*256+:256]);

                                        for (int v = 0; v < V; v++) begin
                                            tx_sequence[k][v] <= f.initial_sequence;
                                            rx_sequence[k][v] <= f.initial_sequence;
                                        end

                                        tx_exhausted[k] <= '0;
                                        rx_exhausted[k] <= '0;
                                    end

                                    active_owner <= candidate_owner;
                                    active_kernel <= candidate_kernel;
                                    active_package <= candidate_package;
                                    configured <= 1'b0;
                                    applying <= 1'b1;
                                    prepared <= 1'b0;
                                    response_valid <= 1'b0;
                                end
                            end
                            NOC_CFG_ABORT: begin
                                prepared <= 1'b0;
                                candidate_owned <= 1'b0;

                                for (int w = 0; w < WORDS; w++) candidate[w] <= '0;
                            end
                            NOC_CFG_STATUS: response_data <= {31'b0, prepared, SIGNATURE[31:0]};
                            default: response_status <= NOC_CFG_COMMAND;
                        endcase
                    end
                end

                if (drain_fire) begin
                    blocked <= i_drain_all ? '1 : blocked | i_drain_flow_mask;
                    draining <= 1'b1;
                    drain_cycles <= '0;
                    drain_settle <= '0;
                    lifecycle_tag <= i_drain_tag;
                end else if (draining) begin
                    // Public ejection resolves packet ownership before a delayed
                    // return credit necessarily reaches its upstream router.
                    // Other flows may keep using the fabric during selected drain.
                    if (!selected_empty) drain_settle <= '0;
                    else if (drain_settle < CREDIT_RETURN_PIPELINE_STAGES + 1)
                        drain_settle <= drain_settle + 1'b1;
                    if (selected_empty &&
                        drain_settle >= CREDIT_RETURN_PIPELINE_STAGES + 1 &&
                        (blocked != {MF{1'b1}} || transport_idle)) begin
                        draining <= 1'b0;
                        lifecycle_valid <= 1'b1;
                        lifecycle_status <= NOC_DRAINED;
                    end else if (drain_cycles == DRAIN_TIMEOUT_CYCLES - 1) begin
                        draining <= 1'b0;
                        lifecycle_valid <= 1'b1;
                        lifecycle_status <= NOC_TIMEOUT;
                        error_flag <= 1'b1;
                        error_code <= NOC_ERROR_TIMEOUT;
                    end else drain_cycles <= drain_cycles + 1'b1;
                end

                if (flush_fire) begin
                    lifecycle_tag <= i_flush_tag;

                    if ((&link_epoch) || (&execution_epoch)) begin
                        lifecycle_valid <= 1'b1;
                        lifecycle_status <= NOC_EPOCH_EXHAUSTED;
                        error_flag <= 1'b1;
                        error_code <= NOC_ERROR_EPOCH;
                        fatal <= 1'b1;
                        blocked <= '1;
                    end else begin
                        flushing <= 1'b1;
                        draining <= 1'b0;
                        blocked <= '1;
                    end
                end

                if (flushing) begin
                    flushing <= 1'b0;
                    execution_epoch <= execution_epoch + 1'b1;
                    link_epoch <= link_epoch + 1'b1;
                    lifecycle_valid <= 1'b1;
                    lifecycle_status <= NOC_FLUSHED;
                    prepared <= 1'b0;
                    delta = 0;

                    for (int k = 0; k < MF; k++) begin
                        delta = delta + int'(outstanding[k]);
                        outstanding[k] <= '0;
                        tx_exhausted[k] <= '0;
                        rx_exhausted[k] <= '0;
                        f = decode_flow(active_records[k*256+:256]);
                        image[2+NN+4*k][40:33] <= execution_epoch + 1'b1;

                        for (int v = 0; v < V; v++) begin
                            tx_sequence[k][v] <= f.initial_sequence;
                            rx_sequence[k][v] <= f.initial_sequence;
                        end
                    end

                    if (ENABLE_COUNTERS) discarded_packets <= discarded_packets + 64'(delta);
                end else if (!applying) begin
                    accepts = 0;
                    deliveries = 0;

                    for (int c = 0; c < NE * TX; c++) begin
                        if (tx_fire[c]) begin
                            accepts = accepts + 1;

                            if (&tx_sequence[tx_flow[c]][tx_vc[c]])
                                tx_exhausted[tx_flow[c]][tx_vc[c]] <= 1'b1;
                            else tx_sequence[tx_flow[c]][tx_vc[c]] <=
                                tx_sequence[tx_flow[c]][tx_vc[c]] + 1'b1;
                        end

                        if (enabled && (i_tile_tx_valid[c] === 1'b1) &&
                            (!tx_binding[c] ||!tx_sequence_legal[c])) begin
                            error_flag <= 1'b1;
                            error_code <= !tx_binding[c] ? NOC_ERROR_BINDING : NOC_ERROR_SEQUENCE;
                            error_flow <= i_tile_tx_user_metadata[c*U+:16];
                            error_endpoint <= N'(c / TX);
                        end
                    end

                    for (int c = 0; c < NE * RX; c++) begin
                        if (rx_fire[c]) begin
                            deliveries = deliveries + 1;

                            if (&rx_sequence[rx_flow[c]][rx_vc[c]])
                                rx_exhausted[rx_flow[c]][rx_vc[c]] <= 1'b1;
                            else rx_sequence[rx_flow[c]][rx_vc[c]] <=
                                rx_sequence[rx_flow[c]][rx_vc[c]] + 1'b1;
                        end

                        if (native_rx_valid[c] &&!rx_legal[c] &&!flush_fire) begin
                            fatal <= 1'b1;
                            error_flag <= 1'b1;
                            error_code <= NOC_ERROR_EGRESS;
                            error_flow <= native_rx_user_metadata[c*U+:16];
                            error_endpoint <= N'(c / RX);
                        end
                    end

                    for (int k = 0; k < MF; k++) begin
                        delta = 0;
                        increments = 0;

                        for (int c = 0; c < NE * TX; c++)
                            if (tx_fire[c] && tx_flow[c] == k) begin
                                delta = delta + 1;
                                increments = increments + 1;
                            end

                        for (int c = 0; c < NE * RX; c++)
                            if (rx_fire[c] && rx_flow[c] == k) delta = delta - 1;

                        if (delta != 0) outstanding[k] <= 16'(int'(outstanding[k]) + delta);

                        if (ENABLE_COUNTERS && increments != 0)
                            flow_packets[k] <= flow_packets[k] + 32'(increments);
                    end

                    if (ENABLE_COUNTERS) begin
                        if (accepts != 0) accepted_packets <= accepted_packets + 64'(accepts);

                        if (deliveries != 0)
                            delivered_packets <= delivered_packets + 64'(deliveries);

                        for (int tc = 0; tc < 8; tc++) begin
                            increments = 0;

                            for (int c = 0; c < NE * TX; c++)
                                if (tx_fire[c] && i_tile_tx_traffic_class[c*TC+:TC] == TC'(tc))
                                    increments = increments + 1;

                            if (increments != 0)
                                class_packets[tc] <= class_packets[tc] + 32'(increments);
                        end
                    end
                end
            end
        end

        for (genvar n = 0; n < NN; n++) begin : g_node
            noc_router #(
                .MESH_X(NOC_X),
                .MESH_Y(NOC_Y),
                .ROUTER_X(n % NOC_X),
                .ROUTER_Y(n / NOC_X),
                .FLIT_DATA_WIDTH(D),
                .NUM_VCS(V),
                .INPUT_VC_DEPTH(DEPTH),
                .FLOW_CONTROL(FLOW_CONTROL),
                .OUTPUT_INITIAL_CREDITS(DEPTH),
                .PACKET_CREDIT_RESERVATION(FLOW_CONTROL == 1 ? FRAGMENTS : 0),
                .ROUTING_ALGORITHM(ROUTING_ALGORITHM),
                .NUM_TRAFFIC_CLASSES(8),
                .ENABLE_QOS(ENABLE_QOS),
                .HIGH_SERVICE_BURST_LIMIT(HIGH_SERVICE_BURST_LIMIT),
                .NODE_ID_WIDTH(N),
                .ENDPOINT_ID_WIDTH(EP),
                .CONTEXT_ID_WIDTH(CX),
                .MESSAGE_TYPE_WIDTH(MT),
                .PACKET_ID_WIDTH(PI),
                .FRAGMENT_INDEX_WIDTH(F),
                .USER_METADATA_WIDTH(U),
                .ERROR_WIDTH(ER),
                .LINK_EPOCH_WIDTH(E),
                .ENABLE_LINK_PARITY(ENABLE_LINK_PARITY),
                .BUFFER_PROTECTION(BUFFER_PROTECTION),
                .OUTPUT_PIPELINE(ROUTER_OUTPUT_PIPELINE),
                .TRAFFIC_CLASS_TO_VC(TRAFFIC_CLASS_TO_VC),
                .TRAFFIC_CLASS_TO_SERVICE(TRAFFIC_CLASS_TO_SERVICE)
            ) u_router (
                .i_clk(i_noc_clk),
                .i_rstb(i_noc_rstb),
                .i_drain(1'b0),
                .i_flush(flush_pulse),
                .i_error_clear(i_error_clear),
                .i_config_valid(native_config_valid),
                .o_config_ready(router_config_ready[n]),
                .i_config_port_enable(present_ports(n)),
                .i_config_fault_port_mask(o_fault_mask[n*5+:5]),
                .o_config_accepted(),
                .o_config_rejected(),
                .i_in_valid(r_in_valid[n]),
                .o_in_ready(r_in_ready[n]),
                .o_out_valid(r_out_valid[n]),
                .i_out_ready(r_out_ready[n]),
                .i_in_data(r_in_data[n]),
                .i_in_keep(r_in_keep[n]),
                .i_in_head(r_in_head[n]),
                .i_in_tail(r_in_tail[n]),
                .i_in_fragment_index(r_in_fragment_index[n]),
                .i_in_vc(r_in_vc[n]),
                .i_in_source_node(r_in_source_node[n]),
                .i_in_source_endpoint(r_in_source_endpoint[n]),
                .i_in_destination_node(r_in_destination_node[n]),
                .i_in_destination_endpoint(r_in_destination_endpoint[n]),
                .i_in_context_id(r_in_context_id[n]),
                .i_in_message_type(r_in_message_type[n]),
                .i_in_traffic_class(r_in_traffic_class[n]),
                .i_in_packet_id(r_in_packet_id[n]),
                .i_in_stream_last(r_in_stream_last[n]),
                .i_in_user_metadata(r_in_user_metadata[n]),
                .i_in_error(r_in_error[n]),
                .i_in_epoch(r_in_epoch[n]),
                .i_in_parity(r_in_parity[n]),
                .o_out_data(r_out_data[n]),
                .o_out_keep(r_out_keep[n]),
                .o_out_head(r_out_head[n]),
                .o_out_tail(r_out_tail[n]),
                .o_out_fragment_index(r_out_fragment_index[n]),
                .o_out_vc(r_out_vc[n]),
                .o_out_source_node(r_out_source_node[n]),
                .o_out_source_endpoint(r_out_source_endpoint[n]),
                .o_out_destination_node(r_out_destination_node[n]),
                .o_out_destination_endpoint(r_out_destination_endpoint[n]),
                .o_out_context_id(r_out_context_id[n]),
                .o_out_message_type(r_out_message_type[n]),
                .o_out_traffic_class(r_out_traffic_class[n]),
                .o_out_packet_id(r_out_packet_id[n]),
                .o_out_stream_last(r_out_stream_last[n]),
                .o_out_user_metadata(r_out_user_metadata[n]),
                .o_out_error(r_out_error[n]),
                .o_out_epoch(r_out_epoch[n]),
                .o_out_parity(r_out_parity[n]),
                .i_out_credit_valid(r_credit_valid[n]),
                .i_out_credit_vc(r_credit_vc[n]),
                .i_out_credit_epoch(r_credit_epoch[n]),
                .o_in_credit_valid(r_return_valid[n]),
                .o_in_credit_vc(r_return_vc[n]),
                .o_in_credit_epoch(r_return_epoch[n]),
                .o_active_port_enable(),
                .o_active_fault_port_mask(),
                .o_link_epoch(o_link_epoch[n*5*E+:5*E]),
                .o_input_vc_occupancy(o_router_input_vc_occupancy[n*5*V*OCC+:5*V*OCC]),
                .o_output_credit_count(o_router_output_credit_count[n*5*V*CW+:5*V*CW]),
                .o_idle(router_idle[n]),
                .o_error(router_error[n]),
                .o_fatal_error(router_fatal[n])
            );

            tile_network_interface #(
                .NUM_TX_CHANNELS(TX),
                .NUM_RX_CHANNELS(RX),
                .TILE_DATA_WIDTH(TD),
                .NOC_FLIT_DATA_WIDTH(D),
                .TX_QUEUE_DEPTH(ENDPOINT_TX_QUEUE_DEPTH),
                .RX_VC_DEPTH(ENDPOINT_RX_VC_DEPTH),
                .RX_QUEUE_DEPTH(ENDPOINT_RX_QUEUE_DEPTH),
                .NUM_VCS(V),
                .NUM_TRAFFIC_CLASSES(8),
                .NOC_FLOW_CONTROL(FLOW_CONTROL),
                .TX_INITIAL_CREDITS_PER_VC(DEPTH),
                .PACKET_CREDIT_RESERVATION(FLOW_CONTROL == 1 ? FRAGMENTS : 0),
                .NODE_ID_WIDTH(N),
                .ENDPOINT_ID_WIDTH(EP),
                .CONTEXT_ID_WIDTH(CX),
                .MESSAGE_TYPE_WIDTH(MT),
                .PACKET_ID_WIDTH(PI),
                .USER_METADATA_WIDTH(U),
                .ERROR_WIDTH(ER),
                .LINK_EPOCH_WIDTH(E),
                .LOCAL_NODE_ID(n),
                .ENABLE_LINK_PARITY(ENABLE_LINK_PARITY),
                .TRAFFIC_CLASS_TO_VC(TRAFFIC_CLASS_TO_VC)
            ) u_endpoint (
                .i_clk(i_noc_clk),
                .i_rstb(i_noc_rstb),
                .i_drain(1'b0),
                .i_flush(flush_pulse),
                .i_error_clear(i_error_clear),
                .i_config_valid(native_config_valid),
                .o_config_ready(endpoint_config_ready[n]),
                .i_config_tx_enable({TX{1'b1}}),
                .i_config_rx_enable({RX{1'b1}}),
                .i_config_context_check(1'b0),
                .i_config_context_id({CX{1'b0}}),
                .o_config_accepted(),
                .o_config_rejected(),
                .i_tile_tx_valid(native_tx_valid[n*TX+:TX]),
                .o_tile_tx_ready(native_tx_ready[n*TX+:TX]),
                .o_tile_rx_valid(native_rx_valid[n*RX+:RX]),
                .i_tile_rx_ready(native_rx_ready[n*RX+:RX]),
                .i_tile_tx_data(i_tile_tx_data[n*TX*TD+:TX*TD]),
                .i_tile_tx_keep(i_tile_tx_keep[n*TX*TB+:TX*TB]),
                .i_tile_tx_last(i_tile_tx_last[n*TX*1+:TX*1]),
                .i_tile_tx_context_id(i_tile_tx_context_id[n*TX*CX+:TX*CX]),
                .i_tile_tx_message_type(i_tile_tx_message_type[n*TX*MT+:TX*MT]),
                .i_tile_tx_traffic_class(i_tile_tx_traffic_class[n*TX*TC+:TX*TC]),
                .i_tile_tx_packet_id(i_tile_tx_packet_id[n*TX*PI+:TX*PI]),
                .i_tile_tx_user_metadata(i_tile_tx_user_metadata[n*TX*U+:TX*U]),
                .i_tile_tx_error(i_tile_tx_error[n*TX*ER+:TX*ER]),
                .i_tile_tx_destination_node(i_tile_tx_destination_node[n*TX*N+:TX*N]),
                .i_tile_tx_destination_endpoint(i_tile_tx_destination_endpoint[n*TX*EP+:TX*EP]),
                .o_tile_rx_data(native_rx_data[n*RX*TD+:RX*TD]),
                .o_tile_rx_keep(native_rx_keep[n*RX*TB+:RX*TB]),
                .o_tile_rx_last(native_rx_last[n*RX*1+:RX*1]),
                .o_tile_rx_context_id(native_rx_context_id[n*RX*CX+:RX*CX]),
                .o_tile_rx_message_type(native_rx_message_type[n*RX*MT+:RX*MT]),
                .o_tile_rx_traffic_class(native_rx_traffic_class[n*RX*TC+:RX*TC]),
                .o_tile_rx_packet_id(native_rx_packet_id[n*RX*PI+:RX*PI]),
                .o_tile_rx_user_metadata(native_rx_user_metadata[n*RX*U+:RX*U]),
                .o_tile_rx_error(native_rx_error[n*RX*ER+:RX*ER]),
                .o_tile_rx_source_node(native_rx_source_node[n*RX*N+:RX*N]),
                .o_tile_rx_source_endpoint(native_rx_source_endpoint[n*RX*EP+:RX*EP]),
                .o_noc_tx_valid(t_tx_valid[n]),
                .i_noc_tx_ready(t_tx_ready[n]),
                .o_noc_tx_data(t_tx_data[n]),
                .o_noc_tx_keep(t_tx_keep[n]),
                .o_noc_tx_head(t_tx_head[n]),
                .o_noc_tx_tail(t_tx_tail[n]),
                .o_noc_tx_fragment_index(t_tx_fragment_index[n]),
                .o_noc_tx_vc(t_tx_vc[n]),
                .o_noc_tx_source_node(t_tx_source_node[n]),
                .o_noc_tx_source_endpoint(t_tx_source_endpoint[n]),
                .o_noc_tx_destination_node(t_tx_destination_node[n]),
                .o_noc_tx_destination_endpoint(t_tx_destination_endpoint[n]),
                .o_noc_tx_context_id(t_tx_context_id[n]),
                .o_noc_tx_message_type(t_tx_message_type[n]),
                .o_noc_tx_traffic_class(t_tx_traffic_class[n]),
                .o_noc_tx_packet_id(t_tx_packet_id[n]),
                .o_noc_tx_stream_last(t_tx_stream_last[n]),
                .o_noc_tx_user_metadata(t_tx_user_metadata[n]),
                .o_noc_tx_error(t_tx_error[n]),
                .o_noc_tx_epoch(t_tx_epoch[n]),
                .o_noc_tx_parity(t_tx_parity[n]),
                .i_noc_rx_valid(t_rx_valid[n]),
                .o_noc_rx_ready(t_rx_ready[n]),
                .i_noc_rx_data(t_rx_data[n]),
                .i_noc_rx_keep(t_rx_keep[n]),
                .i_noc_rx_head(t_rx_head[n]),
                .i_noc_rx_tail(t_rx_tail[n]),
                .i_noc_rx_fragment_index(t_rx_fragment_index[n]),
                .i_noc_rx_vc(t_rx_vc[n]),
                .i_noc_rx_source_node(t_rx_source_node[n]),
                .i_noc_rx_source_endpoint(t_rx_source_endpoint[n]),
                .i_noc_rx_destination_node(t_rx_destination_node[n]),
                .i_noc_rx_destination_endpoint(t_rx_destination_endpoint[n]),
                .i_noc_rx_context_id(t_rx_context_id[n]),
                .i_noc_rx_message_type(t_rx_message_type[n]),
                .i_noc_rx_traffic_class(t_rx_traffic_class[n]),
                .i_noc_rx_packet_id(t_rx_packet_id[n]),
                .i_noc_rx_stream_last(t_rx_stream_last[n]),
                .i_noc_rx_user_metadata(t_rx_user_metadata[n]),
                .i_noc_rx_error(t_rx_error[n]),
                .i_noc_rx_epoch(t_rx_epoch[n]),
                .i_noc_rx_parity(t_rx_parity[n]),
                .i_noc_tx_credit_valid(t_credit_valid[n]),
                .i_noc_tx_credit_vc(t_credit_vc[n]),
                .i_noc_tx_credit_epoch(t_credit_epoch[n]),
                .o_noc_rx_credit_valid(t_return_valid[n]),
                .o_noc_rx_credit_vc(t_return_vc[n]),
                .o_noc_rx_credit_epoch(t_return_epoch[n]),
                .o_tx_queue_occupancy(o_endpoint_tx_queue_occupancy[n*TX*TO+:TX*TO]),
                .o_rx_vc_occupancy(o_endpoint_rx_vc_occupancy[n*V*VO+:V*VO]),
                .o_rx_queue_occupancy(o_endpoint_rx_queue_occupancy[n*RX*RO+:RX*RO]),
                .o_idle(endpoint_idle[n]),
                .o_error(endpoint_error[n])
            );

            wire [LW-1:0] inject;
            wire [LW-1:0] eject;
            wire [F-1:0] receive_fragment;
            wire eject_valid;
            wire unused_credit_ready;
            assign fragment_bad[n] = eject_valid &&
                (32'(receive_fragment) >= FRAGMENTS);
            assign t_rx_fragment_index[n] = receive_fragment[NF-1:0];
            assign inject = {
                t_tx_data[n],
                t_tx_keep[n],
                t_tx_head[n],
                t_tx_tail[n],
                F'(t_tx_fragment_index[n]),
                t_tx_vc[n],
                t_tx_source_node[n],
                t_tx_source_endpoint[n],
                t_tx_destination_node[n],
                t_tx_destination_endpoint[n],
                t_tx_context_id[n],
                t_tx_message_type[n],
                t_tx_traffic_class[n],
                t_tx_packet_id[n],
                t_tx_stream_last[n],
                t_tx_user_metadata[n],
                t_tx_error[n],
                t_tx_epoch[n],
                t_tx_parity[n]
            };
            assign {
                t_rx_data[n],
                t_rx_keep[n],
                t_rx_head[n],
                t_rx_tail[n],
                receive_fragment,
                t_rx_vc[n],
                t_rx_source_node[n],
                t_rx_source_endpoint[n],
                t_rx_destination_node[n],
                t_rx_destination_endpoint[n],
                t_rx_context_id[n],
                t_rx_message_type[n],
                t_rx_traffic_class[n],
                t_rx_packet_id[n],
                t_rx_stream_last[n],
                t_rx_user_metadata[n],
                t_rx_error[n],
                t_rx_epoch[n],
                t_rx_parity[n]
            } = eject;
            wire [LW-1:0] inject_received;
            assign {
                r_in_data[n][0+:D],
                r_in_keep[n][0+:K],
                r_in_head[n][0],
                r_in_tail[n][0],
                r_in_fragment_index[n][0+:F],
                r_in_vc[n][0+:VW],
                r_in_source_node[n][0+:N],
                r_in_source_endpoint[n][0+:EP],
                r_in_destination_node[n][0+:N],
                r_in_destination_endpoint[n][0+:EP],
                r_in_context_id[n][0+:CX],
                r_in_message_type[n][0+:MT],
                r_in_traffic_class[n][0+:TC],
                r_in_packet_id[n][0+:PI],
                r_in_stream_last[n][0],
                r_in_user_metadata[n][0+:U],
                r_in_error[n][0+:ER],
                r_in_epoch[n][0+:E],
                r_in_parity[n][0]
            } = inject_received;

            global_noc_link #(.WIDTH(LW), .FLOW_CONTROL(FLOW_CONTROL)) u_inject (
                .i_clk(i_noc_clk),
                .i_rstb(i_noc_rstb),
                .i_flush(flush_pulse),
                .i_valid(t_tx_valid[n]),
                .o_ready(t_tx_ready[n]),
                .i_data(inject),
                .o_valid(r_in_valid[n][0]),
                .i_ready(r_in_ready[n][0]),
                .o_data(inject_received),
                .o_busy(local_busy[n*2])
            );

            wire [LW-1:0] eject_source;
            assign eject_source = {
                r_out_data[n][0+:D],
                r_out_keep[n][0+:K],
                r_out_head[n][0],
                r_out_tail[n][0],
                r_out_fragment_index[n][0+:F],
                r_out_vc[n][0+:VW],
                r_out_source_node[n][0+:N],
                r_out_source_endpoint[n][0+:EP],
                r_out_destination_node[n][0+:N],
                r_out_destination_endpoint[n][0+:EP],
                r_out_context_id[n][0+:CX],
                r_out_message_type[n][0+:MT],
                r_out_traffic_class[n][0+:TC],
                r_out_packet_id[n][0+:PI],
                r_out_stream_last[n][0],
                r_out_user_metadata[n][0+:U],
                r_out_error[n][0+:ER],
                r_out_epoch[n][0+:E],
                r_out_parity[n][0]
            };

            global_noc_link #(.WIDTH(LW), .FLOW_CONTROL(FLOW_CONTROL)) u_eject (
                .i_clk(i_noc_clk),
                .i_rstb(i_noc_rstb),
                .i_flush(flush_pulse),
                .i_valid(r_out_valid[n][0]),
                .o_ready(r_out_ready[n][0]),
                .i_data(eject_source),
                .o_valid(eject_valid),
                .i_ready(t_rx_ready[n]),
                .o_data(eject),
                .o_busy(local_busy[n*2+1])
            );

            assign t_rx_valid[n] = eject_valid &&!fragment_bad[n];
            assign t_credit_valid[n] = r_return_valid[n][0];
            assign t_credit_vc[n] = r_return_vc[n][0+:VW];
            assign t_credit_epoch[n] = r_return_epoch[n][0+:E];
            assign r_credit_valid[n][0] = t_return_valid[n];
            assign r_credit_vc[n][0+:VW] = t_return_vc[n];
            assign r_credit_epoch[n][0+:E] = t_return_epoch[n];
            assign link_busy[n*5] = local_busy[n*2] || local_busy[n*2+1];

            for (genvar p = 1; p < 5; p++) begin : g_port
                localparam int X = n % NOC_X;
                localparam int Y = n / NOC_X;
                localparam bit PRESENT = (p == 1 && Y > 0) ||
                    (p == 2 && X < NOC_X - 1) || (p == 3 && Y < NOC_Y - 1) ||
                    (p == 4 && X > 0);
                localparam int PEER = p == 1 ? n - NOC_X : p == 2 ? n + 1 :
                    p == 3 ? n + NOC_X : n - 1;
                localparam int REVERSE = p == 1 ? 3 : p == 2 ? 4 : p == 3 ? 1 : 2;

                if (PRESENT) begin : g_link
                    wire [LW-1:0] source;
                    wire [LW-1:0] received;
                    wire forward_busy;
                    wire return_busy;
                    wire unused_ready;
                    assign source = {
                        r_out_data[PEER][REVERSE*D+:D],
                        r_out_keep[PEER][REVERSE*K+:K],
                        r_out_head[PEER][REVERSE],
                        r_out_tail[PEER][REVERSE],
                        r_out_fragment_index[PEER][REVERSE*F+:F],
                        r_out_vc[PEER][REVERSE*VW+:VW],
                        r_out_source_node[PEER][REVERSE*N+:N],
                        r_out_source_endpoint[PEER][REVERSE*EP+:EP],
                        r_out_destination_node[PEER][REVERSE*N+:N],
                        r_out_destination_endpoint[PEER][REVERSE*EP+:EP],
                        r_out_context_id[PEER][REVERSE*CX+:CX],
                        r_out_message_type[PEER][REVERSE*MT+:MT],
                        r_out_traffic_class[PEER][REVERSE*TC+:TC],
                        r_out_packet_id[PEER][REVERSE*PI+:PI],
                        r_out_stream_last[PEER][REVERSE],
                        r_out_user_metadata[PEER][REVERSE*U+:U],
                        r_out_error[PEER][REVERSE*ER+:ER],
                        r_out_epoch[PEER][REVERSE*E+:E],
                        r_out_parity[PEER][REVERSE]
                    };
                    assign {
                        r_in_data[n][p*D+:D],
                        r_in_keep[n][p*K+:K],
                        r_in_head[n][p],
                        r_in_tail[n][p],
                        r_in_fragment_index[n][p*F+:F],
                        r_in_vc[n][p*VW+:VW],
                        r_in_source_node[n][p*N+:N],
                        r_in_source_endpoint[n][p*EP+:EP],
                        r_in_destination_node[n][p*N+:N],
                        r_in_destination_endpoint[n][p*EP+:EP],
                        r_in_context_id[n][p*CX+:CX],
                        r_in_message_type[n][p*MT+:MT],
                        r_in_traffic_class[n][p*TC+:TC],
                        r_in_packet_id[n][p*PI+:PI],
                        r_in_stream_last[n][p],
                        r_in_user_metadata[n][p*U+:U],
                        r_in_error[n][p*ER+:ER],
                        r_in_epoch[n][p*E+:E],
                        r_in_parity[n][p]
                    } = received;

                    // Parity containment gates native router outputs immediately.
                    // Register the complete protected flit to break combinational
                    // fault propagation around bidirectional physical mesh links.
                    global_noc_link #(.WIDTH(LW), .FLOW_CONTROL(FLOW_CONTROL),
                        .STAGES(LINK_PIPELINE_STAGES + ENABLE_LINK_PARITY)) u_forward (
                        .i_clk(i_noc_clk),
                        .i_rstb(i_noc_rstb),
                        .i_flush(flush_pulse),
                        .i_valid(r_out_valid[PEER][REVERSE]),
                        .o_ready(r_out_ready[PEER][REVERSE]),
                        .i_data(source),
                        .o_valid(r_in_valid[n][p]),
                        .i_ready(r_in_ready[n][p]),
                        .o_data(received),
                        .o_busy(forward_busy)
                    );

                    global_noc_link #(.WIDTH(VW + E), .FLOW_CONTROL(1),
                        .STAGES(CREDIT_RETURN_PIPELINE_STAGES)) u_return (
                        .i_clk(i_noc_clk),
                        .i_rstb(i_noc_rstb),
                        .i_flush(flush_pulse),
                        .i_valid(r_return_valid[n][p]),
                        .o_ready(unused_ready),
                        .i_data({r_return_vc[n][p*VW+:VW], r_return_epoch[n][p*E+:E]}),
                        .o_valid(r_credit_valid[PEER][REVERSE]),
                        .i_ready(1'b1),
                        .o_data({r_credit_vc[PEER][REVERSE*VW+:VW],
                            r_credit_epoch[PEER][REVERSE*E+:E]}),
                        .o_busy(return_busy)
                    );

                    assign link_busy[n*5+p] = forward_busy || return_busy;
                end else begin : g_boundary
                    assign r_in_valid[n][p] = 1'b0;
                    assign r_out_ready[n][p] = 1'b0;
                    assign r_credit_valid[n][p] = 1'b0;
                    assign r_credit_vc[n][p*VW+:VW] = '0;
                    assign r_credit_epoch[n][p*E+:E] = '0;
                    assign link_busy[n*5+p] = 1'b0;
                    assign r_in_data[n][p*D+:D] = '0;
                    assign r_in_keep[n][p*K+:K] = '0;
                    assign r_in_head[n][p] = '0;
                    assign r_in_tail[n][p] = '0;
                    assign r_in_fragment_index[n][p*F+:F] = '0;
                    assign r_in_vc[n][p*VW+:VW] = '0;
                    assign r_in_source_node[n][p*N+:N] = '0;
                    assign r_in_source_endpoint[n][p*EP+:EP] = '0;
                    assign r_in_destination_node[n][p*N+:N] = '0;
                    assign r_in_destination_endpoint[n][p*EP+:EP] = '0;
                    assign r_in_context_id[n][p*CX+:CX] = '0;
                    assign r_in_message_type[n][p*MT+:MT] = '0;
                    assign r_in_traffic_class[n][p*TC+:TC] = '0;
                    assign r_in_packet_id[n][p*PI+:PI] = '0;
                    assign r_in_stream_last[n][p] = '0;
                    assign r_in_user_metadata[n][p*U+:U] = '0;
                    assign r_in_error[n][p*ER+:ER] = '0;
                    assign r_in_epoch[n][p*E+:E] = '0;
                    assign r_in_parity[n][p] = '0;
                end
            end
        end
    end
endmodule
`default_nettype wire
