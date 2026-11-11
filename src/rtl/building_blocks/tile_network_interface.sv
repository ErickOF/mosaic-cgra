`timescale 1ns / 1ps
`default_nettype none

// Fixed-envelope packet bridge. All payload queues use the released synchronous
// flush wrapper over common FIFOs; no generated clock or reset gating is used.
module tile_network_interface #(
    parameter NUM_TX_CHANNELS = 4,
    parameter NUM_RX_CHANNELS = 4,
    parameter TILE_DATA_WIDTH = 128,
    parameter NOC_FLIT_DATA_WIDTH = 32,
    parameter TX_QUEUE_DEPTH = 2,
    parameter RX_VC_DEPTH = 2,
    parameter RX_QUEUE_DEPTH = 2,
    parameter NUM_VCS = 1,
    parameter NUM_TRAFFIC_CLASSES = 8,
    parameter NOC_FLOW_CONTROL = 0,
    parameter TX_INITIAL_CREDITS_PER_VC = 2,
    // Optional fixed-envelope admission prevents a partially injected data
    // packet from monopolizing the physical serializer ahead of critical VCs.
    parameter PACKET_CREDIT_RESERVATION = 0,
    parameter NODE_ID_WIDTH = 8,
    parameter ENDPOINT_ID_WIDTH = 4,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter MESSAGE_TYPE_WIDTH = 4,
    parameter PACKET_ID_WIDTH = 8,
    parameter USER_METADATA_WIDTH = 16,
    parameter ERROR_WIDTH = 4,
    parameter LINK_EPOCH_WIDTH = 2,
    parameter LOCAL_NODE_ID = 0,
    parameter ENABLE_LINK_PARITY = 0,
    parameter ASYNC_RESET = 0,
    localparam bit GEOMETRY_VALID =
        ((PACKET_CREDIT_RESERVATION >= 0 &&
            PACKET_CREDIT_RESERVATION <= TX_INITIAL_CREDITS_PER_VC) === 1'b1) &&
        (((^PACKET_CREDIT_RESERVATION == 1'b0) || (^PACKET_CREDIT_RESERVATION == 1'b1)) === 1'b1) &&
        ((NUM_TX_CHANNELS > 0) === 1'b1) && (((^NUM_TX_CHANNELS == 1'b0) || (^NUM_TX_CHANNELS == 1'b1)) === 1'b1) &&
        ((NUM_RX_CHANNELS > 0) === 1'b1) && (((^NUM_RX_CHANNELS == 1'b0) || (^NUM_RX_CHANNELS == 1'b1)) === 1'b1) &&
        ((TILE_DATA_WIDTH > 0) === 1'b1) && (((^TILE_DATA_WIDTH == 1'b0) || (^TILE_DATA_WIDTH == 1'b1)) === 1'b1) &&
        ((NOC_FLIT_DATA_WIDTH > 0) === 1'b1) && (((^NOC_FLIT_DATA_WIDTH == 1'b0) || (^NOC_FLIT_DATA_WIDTH == 1'b1)) === 1'b1) &&
        ((TX_QUEUE_DEPTH > 0) === 1'b1) && (((^TX_QUEUE_DEPTH == 1'b0) || (^TX_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((RX_VC_DEPTH > 0) === 1'b1) && (((^RX_VC_DEPTH == 1'b0) || (^RX_VC_DEPTH == 1'b1)) === 1'b1) &&
        ((RX_QUEUE_DEPTH > 0) === 1'b1) && (((^RX_QUEUE_DEPTH == 1'b0) || (^RX_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((NUM_VCS > 0) === 1'b1) && (((^NUM_VCS == 1'b0) || (^NUM_VCS == 1'b1)) === 1'b1) &&
        ((NUM_TRAFFIC_CLASSES > 0) === 1'b1) && (((^NUM_TRAFFIC_CLASSES == 1'b0) || (^NUM_TRAFFIC_CLASSES == 1'b1)) === 1'b1) &&
        ((NODE_ID_WIDTH > 0) === 1'b1) && (((^NODE_ID_WIDTH == 1'b0) || (^NODE_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((ENDPOINT_ID_WIDTH > 0) === 1'b1) && (((^ENDPOINT_ID_WIDTH == 1'b0) || (^ENDPOINT_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((CONTEXT_ID_WIDTH > 0) === 1'b1) && (((^CONTEXT_ID_WIDTH == 1'b0) || (^CONTEXT_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((MESSAGE_TYPE_WIDTH > 0) === 1'b1) && (((^MESSAGE_TYPE_WIDTH == 1'b0) || (^MESSAGE_TYPE_WIDTH == 1'b1)) === 1'b1) &&
        ((PACKET_ID_WIDTH > 0) === 1'b1) && (((^PACKET_ID_WIDTH == 1'b0) || (^PACKET_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((USER_METADATA_WIDTH > 0) === 1'b1) && (((^USER_METADATA_WIDTH == 1'b0) || (^USER_METADATA_WIDTH == 1'b1)) === 1'b1) &&
        ((ERROR_WIDTH > 0) === 1'b1) && (((^ERROR_WIDTH == 1'b0) || (^ERROR_WIDTH == 1'b1)) === 1'b1) &&
        ((LINK_EPOCH_WIDTH > 0) === 1'b1) && (((^LINK_EPOCH_WIDTH == 1'b0) || (^LINK_EPOCH_WIDTH == 1'b1)) === 1'b1) &&
        ((TX_INITIAL_CREDITS_PER_VC >= 0) === 1'b1) &&
        (((^TX_INITIAL_CREDITS_PER_VC == 1'b0) || (^TX_INITIAL_CREDITS_PER_VC == 1'b1)) === 1'b1) &&
        ((NOC_FLOW_CONTROL != 1 || TX_INITIAL_CREDITS_PER_VC > 0) === 1'b1) &&
        ((TILE_DATA_WIDTH % 8 == 0 && NOC_FLIT_DATA_WIDTH % 8 == 0) === 1'b1) &&
        ((NOC_FLOW_CONTROL === 0) || (NOC_FLOW_CONTROL === 1)) &&
        ((ENABLE_LINK_PARITY === 0) || (ENABLE_LINK_PARITY === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((LOCAL_NODE_ID >= 0) === 1'b1) && (((^LOCAL_NODE_ID == 1'b0) || (^LOCAL_NODE_ID == 1'b1)) === 1'b1) &&
        ((ENDPOINT_ID_WIDTH >= 32 ||
            (128'(NUM_TX_CHANNELS) <= (128'd1 << ENDPOINT_ID_WIDTH) &&
             128'(NUM_RX_CHANNELS) <= (128'd1 << ENDPOINT_ID_WIDTH))) === 1'b1) &&
        ((NODE_ID_WIDTH >= 128 || 128'(LOCAL_NODE_ID) <
            (128'd1 << NODE_ID_WIDTH)) === 1'b1) &&
        ((128'(NUM_TRAFFIC_CLASSES) * 128'(NUM_VCS) < 128'd2147483647) === 1'b1) &&
        (((128'(TILE_DATA_WIDTH) + 128'(NOC_FLIT_DATA_WIDTH) + 128'(NODE_ID_WIDTH) * 2 +
            128'(ENDPOINT_ID_WIDTH) * 2 + 128'(CONTEXT_ID_WIDTH) +
            128'(MESSAGE_TYPE_WIDTH) + 128'(PACKET_ID_WIDTH) +
            128'(USER_METADATA_WIDTH) + 128'(ERROR_WIDTH) + 128'(LINK_EPOCH_WIDTH) +
            128'(TX_INITIAL_CREDITS_PER_VC) + 128'(NUM_VCS) + 128) *
            (128'(NUM_TX_CHANNELS) * 128'(TX_QUEUE_DEPTH) +
             128'(NUM_RX_CHANNELS) * 128'(RX_QUEUE_DEPTH) +
             128'(NUM_VCS) * (128'(RX_VC_DEPTH) + 128'(NUM_VCS) + 1)) <
            128'd2147483647) === 1'b1),
    localparam int TX = GEOMETRY_VALID ? NUM_TX_CHANNELS : 1,
    localparam int RX = GEOMETRY_VALID ? NUM_RX_CHANNELS : 1,
    localparam int TD = GEOMETRY_VALID ? TILE_DATA_WIDTH : 8,
    localparam int FD = GEOMETRY_VALID ? NOC_FLIT_DATA_WIDTH : 8,
    localparam int TQD = GEOMETRY_VALID ? TX_QUEUE_DEPTH : 1,
    localparam int VQD = GEOMETRY_VALID ? RX_VC_DEPTH : 1,
    localparam int RQD = GEOMETRY_VALID ? RX_QUEUE_DEPTH : 1,
    localparam int V = GEOMETRY_VALID ? NUM_VCS : 1,
    localparam int CLASSES = GEOMETRY_VALID ? NUM_TRAFFIC_CLASSES : 1,
    localparam int N = GEOMETRY_VALID ? NODE_ID_WIDTH : 1,
    localparam int EP = GEOMETRY_VALID ? ENDPOINT_ID_WIDTH : 1,
    localparam int CX = GEOMETRY_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int MT = GEOMETRY_VALID ? MESSAGE_TYPE_WIDTH : 1,
    localparam int PI = GEOMETRY_VALID ? PACKET_ID_WIDTH : 1,
    localparam int U = GEOMETRY_VALID ? USER_METADATA_WIDTH : 1,
    localparam int ER = GEOMETRY_VALID ? ERROR_WIDTH : 1,
    localparam int E = GEOMETRY_VALID ? LINK_EPOCH_WIDTH : 1,
    localparam int CREDITS = GEOMETRY_VALID && TX_INITIAL_CREDITS_PER_VC > 0 ?
        TX_INITIAL_CREDITS_PER_VC : 1,
    localparam int TB = TD / 8,
    localparam int FB = FD / 8,
    localparam int FLITS_PER_PACKET = (TD + FD - 1) / FD,
    localparam int TXW = TX > 1 ? $clog2(TX) : 1,
    localparam int RXW = RX > 1 ? $clog2(RX) : 1,
    localparam int VW = V > 1 ? $clog2(V) : 1,
    localparam int TC = CLASSES > 1 ? $clog2(CLASSES) : 1,
    localparam int F = FLITS_PER_PACKET > 1 ? $clog2(FLITS_PER_PACKET) : 1,
    localparam int TO = $clog2(64'(TQD) + 1),
    localparam int VO = $clog2(64'(VQD) + 1),
    localparam int RO = $clog2(64'(RQD) + 1),
    localparam int CW = $clog2(64'(CREDITS) + 1),
    parameter TRAFFIC_CLASS_TO_VC = {CLASSES*VW{1'b0}},
    localparam bit PARAMETERS_VALID = GEOMETRY_VALID && maps_valid()
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_drain,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_config_valid,
    output logic o_config_ready,
    input logic [TX-1:0] i_config_tx_enable,
    input logic [RX-1:0] i_config_rx_enable,
    input logic i_config_context_check,
    input logic [CX-1:0] i_config_context_id,
    output logic o_config_accepted,
    output logic o_config_rejected,
    input logic [TX-1:0] i_tile_tx_valid,
    input logic [TX*TD-1:0] i_tile_tx_data,
    input logic [TX*TB-1:0] i_tile_tx_keep,
    input logic [TX-1:0] i_tile_tx_last,
    input logic [TX*CX-1:0] i_tile_tx_context_id,
    input logic [TX*MT-1:0] i_tile_tx_message_type,
    input logic [TX*TC-1:0] i_tile_tx_traffic_class,
    input logic [TX*PI-1:0] i_tile_tx_packet_id,
    input logic [TX*U-1:0] i_tile_tx_user_metadata,
    input logic [TX*ER-1:0] i_tile_tx_error,
    input logic [TX*N-1:0] i_tile_tx_destination_node,
    input logic [TX*EP-1:0] i_tile_tx_destination_endpoint,
    output logic [TX-1:0] o_tile_tx_ready,
    output logic [RX-1:0] o_tile_rx_valid,
    output logic [RX*TD-1:0] o_tile_rx_data,
    output logic [RX*TB-1:0] o_tile_rx_keep,
    output logic [RX-1:0] o_tile_rx_last,
    output logic [RX*CX-1:0] o_tile_rx_context_id,
    output logic [RX*MT-1:0] o_tile_rx_message_type,
    output logic [RX*TC-1:0] o_tile_rx_traffic_class,
    output logic [RX*PI-1:0] o_tile_rx_packet_id,
    output logic [RX*U-1:0] o_tile_rx_user_metadata,
    output logic [RX*ER-1:0] o_tile_rx_error,
    output logic [RX*N-1:0] o_tile_rx_source_node,
    output logic [RX*EP-1:0] o_tile_rx_source_endpoint,
    input logic [RX-1:0] i_tile_rx_ready,
    output logic o_noc_tx_valid,
    output logic [FD-1:0] o_noc_tx_data,
    output logic [FB-1:0] o_noc_tx_keep,
    output logic o_noc_tx_head,
    output logic o_noc_tx_tail,
    output logic [F-1:0] o_noc_tx_fragment_index,
    output logic [VW-1:0] o_noc_tx_vc,
    output logic [N-1:0] o_noc_tx_source_node,
    output logic [EP-1:0] o_noc_tx_source_endpoint,
    output logic [N-1:0] o_noc_tx_destination_node,
    output logic [EP-1:0] o_noc_tx_destination_endpoint,
    output logic [CX-1:0] o_noc_tx_context_id,
    output logic [MT-1:0] o_noc_tx_message_type,
    output logic [TC-1:0] o_noc_tx_traffic_class,
    output logic [PI-1:0] o_noc_tx_packet_id,
    output logic o_noc_tx_stream_last,
    output logic [U-1:0] o_noc_tx_user_metadata,
    output logic [ER-1:0] o_noc_tx_error,
    output logic [E-1:0] o_noc_tx_epoch,
    output logic o_noc_tx_parity,
    input logic i_noc_tx_ready,
    input logic i_noc_rx_valid,
    input logic [FD-1:0] i_noc_rx_data,
    input logic [FB-1:0] i_noc_rx_keep,
    input logic i_noc_rx_head,
    input logic i_noc_rx_tail,
    input logic [F-1:0] i_noc_rx_fragment_index,
    input logic [VW-1:0] i_noc_rx_vc,
    input logic [N-1:0] i_noc_rx_source_node,
    input logic [EP-1:0] i_noc_rx_source_endpoint,
    input logic [N-1:0] i_noc_rx_destination_node,
    input logic [EP-1:0] i_noc_rx_destination_endpoint,
    input logic [CX-1:0] i_noc_rx_context_id,
    input logic [MT-1:0] i_noc_rx_message_type,
    input logic [TC-1:0] i_noc_rx_traffic_class,
    input logic [PI-1:0] i_noc_rx_packet_id,
    input logic i_noc_rx_stream_last,
    input logic [U-1:0] i_noc_rx_user_metadata,
    input logic [ER-1:0] i_noc_rx_error,
    input logic [E-1:0] i_noc_rx_epoch,
    input logic i_noc_rx_parity,
    output logic o_noc_rx_ready,
    input logic i_noc_tx_credit_valid,
    input logic [VW-1:0] i_noc_tx_credit_vc,
    input logic [E-1:0] i_noc_tx_credit_epoch,
    output logic o_noc_rx_credit_valid,
    output logic [VW-1:0] o_noc_rx_credit_vc,
    output logic [E-1:0] o_noc_rx_credit_epoch,
    output logic [TX-1:0] o_active_tx_enable,
    output logic [RX-1:0] o_active_rx_enable,
    output logic [CX-1:0] o_active_context_id,
    output logic [E-1:0] o_link_epoch,
    output logic [TX*TO-1:0] o_tx_queue_occupancy,
    output logic [V*VO-1:0] o_rx_vc_occupancy,
    output logic [RX*RO-1:0] o_rx_queue_occupancy,
    output logic [V*CW-1:0] o_tx_credit_count,
    output logic o_idle,
    output logic o_quiescent,
    output logic o_drain_done,
    output logic o_flushed,
    output logic o_error,
    output logic [tile_network_interface_pkg::NI_ERROR_WIDTH-1:0] o_error_code,
    output logic [TX-1:0] o_event_tile_tx_accept,
    output logic [RX-1:0] o_event_tile_rx_transfer,
    output logic o_event_noc_tx_transfer,
    output logic o_event_noc_rx_accept,
    output logic [TX-1:0] o_event_tx_stall,
    output logic [RX-1:0] o_event_rx_stall,
    output logic [TX-1:0] o_event_tx_drop,
    output logic o_event_rx_drop,
    output logic o_event_parity_error
);
    import tile_network_interface_pkg::*;

    function automatic bit maps_valid();
        bit valid;
        valid = $bits(TRAFFIC_CLASS_TO_VC) == CLASSES * VW &&
            (((^TRAFFIC_CLASS_TO_VC == 1'b0) || (^TRAFFIC_CLASS_TO_VC == 1'b1)) === 1'b1);

        for (int c = 0; c < CLASSES; c++)
            if (32'(TRAFFIC_CLASS_TO_VC[c*VW+:VW]) >= V) valid = 1'b0;

        return valid;
    endfunction

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        tile_network_interface_parameters_must_be_valid invalid_parameters ();
    end else begin : g_interface
        // Geometry-dependent records remain local; encodings live in the package.
        typedef struct packed {
            logic [VW-1:0] vc;
            logic [N-1:0] source_node;
            logic [EP-1:0] source_endpoint;
            logic [N-1:0] destination_node;
            logic [EP-1:0] destination_endpoint;
            logic [CX-1:0] context_id;
            logic [MT-1:0] message_type;
            logic [TC-1:0] traffic_class;
            logic [PI-1:0] packet_id;
            logic stream_last;
            logic [U-1:0] user_metadata;
            logic [ER-1:0] error;
            logic [E-1:0] epoch;
        } metadata_t;

        typedef struct packed {
            logic [TD-1:0] data;
            logic [TB-1:0] keep;
            metadata_t metadata;
        } beat_t;

        typedef struct packed {
            logic [FD-1:0] data;
            logic [FB-1:0] keep;
            logic head;
            logic tail;
            logic [F-1:0] fragment_index;
            metadata_t metadata;
        } flit_t;

        typedef struct packed {
            logic open;
            logic bad;
            logic complete;
            logic [F:0] next_fragment;
        } receive_control_t;

        typedef struct packed {
            logic configured;
            logic context_check;
            logic [TX-1:0] tx_enable;
            logic [RX-1:0] rx_enable;
            logic [CX-1:0] context_id;
        } configuration_t;

        localparam int BW = $bits(beat_t);
        localparam int FW = $bits(flit_t);
        localparam int RW = $bits(receive_control_t);
        localparam int CONFIG_BITS = $bits(configuration_t);
        localparam int EVENT_BITS = TX * 3 + RX * 2 + VW + E + 8;
        wire run = i_rstb === 1'b1;
        wire reset_b = i_rstb !== 1'b0;
        wire flush = run && i_flush === 1'b1;
        wire global_known = ^{i_drain, i_flush, i_config_valid, i_error_clear} !== 1'bx;
        wire active = run && i_flush === 1'b0 && global_known;
        wire [CONFIG_BITS-1:0] configuration_bits;
        configuration_t configuration;
        wire configured = configuration.configured;
        wire [TX-1:0] enabled_tx = configuration.tx_enable;
        wire [RX-1:0] enabled_rx = configuration.rx_enable;
        wire configuration_accept = o_config_ready && i_config_valid === 1'b1;
        wire configuration_known = ^{i_config_tx_enable, i_config_rx_enable,
            i_config_context_check, i_config_context_id} !== 1'bx;
        wire configuration_good = configuration_accept && configuration_known;
        wire configuration_bad = configuration_accept && !configuration_known;
        configuration_t configuration_next;
        wire operate = active && configured && !configuration_accept;
        wire fatal;
        wire [NI_ERROR_WIDTH-1:0] sticky_error;
        logic [NI_ERROR_WIDTH-1:0] detected_error;
        wire [E-1:0] epoch;
        wire [TX-1:0] tx_valid;
        wire [TX-1:0] tx_ready;
        wire [TX-1:0] tx_pop;
        wire [BW-1:0] tx_heads [TX];
        logic [BW-1:0] tx_inputs [TX];
        logic [NI_ERROR_WIDTH-1:0] tx_errors [TX];
        logic [TX-1:0] tile_accept;
        logic [TX-1:0] tile_drop;
        logic [TX-1:0] tile_stall;
        wire [CW-1:0] credits [V];
        logic [V-1:0] credit_return;
        logic [NI_ERROR_WIDTH-1:0] credit_error;
        wire [TXW+F:0] serializer_bits;
        logic [TXW+F:0] serializer_next;
        wire serializer_open = serializer_bits[TXW+F];
        wire [TXW-1:0] serializer_owner = serializer_bits[F+:TXW];
        wire [F-1:0] fragment = serializer_bits[F-1:0];
        logic [TX-1:0] tx_requests;
        wire tx_grant_valid;
        wire [TXW-1:0] tx_owner;
        wire tx_arbiter_error;
        flit_t transmitted;
        flit_t presented_tx;
        wire tx_parity;
        wire tx_transfer = o_noc_tx_valid && (NOC_FLOW_CONTROL == FLOW_CREDIT ||
            i_noc_tx_ready === 1'b1);
        wire tx_tail = tx_transfer && presented_tx.tail;
        wire [V-1:0] vc_valid;
        wire [V-1:0] vc_ready;
        logic [V-1:0] vc_push;
        logic [V-1:0] vc_pop;
        wire [FW:0] vc_heads [V];
        wire [RW-1:0] receive_controls [V];
        wire [BW-1:0] receive_payloads [V];
        logic [RW-1:0] receive_controls_next [V];
        logic [BW-1:0] receive_payloads_next [V];
        logic [V-1:0] receive_control_enable;
        logic [V-1:0] receive_payload_enable;
        wire [V-1:0] complete_predecessors [V];
        logic [V-1:0] complete_predecessors_next [V];
        logic [V-1:0] complete_predecessors_enable;
        logic [V-1:0] completion_created;
        logic [V-1:0] processing_requests;
        logic [V-1:0] completion_requests;
        wire processing_valid;
        wire [VW-1:0] processing_vc;
        wire emission_valid;
        wire [VW-1:0] emission_vc;
        wire processing_arbiter_error;
        wire emission_arbiter_error;
        wire [RX-1:0] rx_valid;
        wire [RX-1:0] rx_ready;
        wire [RX-1:0] rx_pop;
        wire [BW-1:0] rx_heads [RX];
        logic [RX-1:0] rx_push;
        logic [BW-1:0] emitted_beat;
        logic [RX-1:0] tile_receive;
        logic [RX-1:0] receive_stall;
        flit_t incoming;
        logic incoming_known;
        logic incoming_vc_valid;
        logic incoming_stale;
        logic rx_accept;
        logic rx_direct_drop;
        logic overflow;
        logic [NI_ERROR_WIDTH-1:0] admission_error;
        logic [NI_ERROR_WIDTH-1:0] processing_error;
        logic processing_drop;
        logic processing_parity_error;
        wire incoming_parity_bad;
        wire queued_parity_bad;
        wire [FW:0] selected_receive_bits = vc_heads[processing_vc];
        flit_t selected_receive;
        wire [EVENT_BITS-1:0] events;
        wire [EVENT_BITS-1:0] next_events;
        logic queues_empty;
        logic contexts_empty;

        always_comb begin
            configuration = configuration_bits;
            configuration_next.configured = 1'b1;
            configuration_next.context_check = i_config_context_check;
            configuration_next.tx_enable = i_config_tx_enable;
            configuration_next.rx_enable = i_config_rx_enable;
            configuration_next.context_id = i_config_context_id;
            queues_empty = !(|tx_valid) && !(|vc_valid) && !(|rx_valid);
            contexts_empty = 1'b1;

            for (int v = 0; v < V; v++)
                if (receive_controls[v] != '0) contexts_empty = 1'b0;
        end

        assign o_active_tx_enable = configuration.tx_enable;
        assign o_active_rx_enable = configuration.rx_enable;
        assign o_active_context_id = configuration.context_id;
        assign o_link_epoch = epoch;
        assign o_idle = queues_empty && contexts_empty && !serializer_open;
        assign o_config_ready = active && i_drain === 1'b0 && o_idle &&
            (i_config_valid === 1'b1 || ((|i_tile_tx_valid) === 1'b0 && i_noc_rx_valid === 1'b0));
        assign o_quiescent = active && i_drain === 1'b0 && o_idle &&
            !(|tile_accept) && !rx_accept && !tx_transfer;
        assign o_drain_done = run && i_drain === 1'b1 && o_idle;
        assign o_error = sticky_error != NI_ERR_NONE;
        assign o_error_code = sticky_error;

        dff #(.WIDTH(CONFIG_BITS), .ASYNC_RESET(ASYNC_RESET)) u_configuration (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(configuration_good),
            .i_d(configuration_next),
            .o_q(configuration_bits)
        );

        counter #(.WIDTH(E), .ASYNC_RESET(ASYNC_RESET), .SATURATE(0)) u_epoch (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(flush),
            .i_clear(1'b0),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({E{1'b0}}),
            .o_count(epoch),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        // Illegal offered beats are consumed without queue ownership. Normalize
        // every disabled byte before storing a legal beat, including X/Z bytes.
        always_comb begin
            o_tile_tx_ready = '0;
            tile_accept = '0;
            tile_drop = '0;
            tile_stall = '0;

            for (int c = 0; c < TX; c++) begin
                beat_t beat;
                logic [TD-1:0] data;
                logic [NI_ERROR_WIDTH-1:0] error;
                beat = '0;
                data = '0;
                error = NI_ERR_NONE;
                beat.keep = i_tile_tx_keep[c*TB+:TB];
                beat.metadata.source_node = N'(LOCAL_NODE_ID);
                beat.metadata.source_endpoint = EP'(c);
                beat.metadata.destination_node = i_tile_tx_destination_node[c*N+:N];
                beat.metadata.destination_endpoint = i_tile_tx_destination_endpoint[c*EP+:EP];
                beat.metadata.context_id = i_tile_tx_context_id[c*CX+:CX];
                beat.metadata.message_type = i_tile_tx_message_type[c*MT+:MT];
                beat.metadata.traffic_class = i_tile_tx_traffic_class[c*TC+:TC];
                beat.metadata.packet_id = i_tile_tx_packet_id[c*PI+:PI];
                beat.metadata.stream_last = i_tile_tx_last[c];
                beat.metadata.user_metadata = i_tile_tx_user_metadata[c*U+:U];
                beat.metadata.error = i_tile_tx_error[c*ER+:ER];
                beat.metadata.epoch = epoch;

                for (int b = 0; b < TB; b++)
                    if (i_tile_tx_keep[c*TB+b] === 1'b1)
                        data[b*8+:8] = i_tile_tx_data[c*TD+b*8+:8];

                beat.data = data;

                if (^{beat.keep, beat.metadata} === 1'bx) error = NI_ERR_UNKNOWN;
                else if (!enabled_tx[c]) error = NI_ERR_DISABLED;
                else if (beat.keep == '0) error = NI_ERR_KEEP;
                else if (32'(beat.metadata.traffic_class) >= CLASSES) error = NI_ERR_CLASS;
                else if (configuration.context_check &&
                    beat.metadata.context_id != configuration.context_id) error = NI_ERR_CONTEXT;

                if (error == NI_ERR_NONE) beat.metadata.vc =
                    TRAFFIC_CLASS_TO_VC[32'(beat.metadata.traffic_class)*VW+:VW];

                tx_inputs[c] = beat;
                tx_errors[c] = error;

                if (operate && !fatal && i_drain === 1'b0) begin
                    o_tile_tx_ready[c] = error != NI_ERR_NONE || tx_ready[c];
                    tile_accept[c] = o_tile_tx_ready[c] && i_tile_tx_valid[c] === 1'b1;
                    tile_drop[c] = tile_accept[c] && error != NI_ERR_NONE;
                    tile_stall[c] = i_tile_tx_valid[c] === 1'b1 && !o_tile_tx_ready[c];
                end
            end
        end

        for (genvar c = 0; c < TX; c++) begin : g_tx_queue
            event_barrier_queue #(.WIDTH(BW), .DEPTH(TQD), .ASYNC_RESET(ASYNC_RESET)) u_queue (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_flush(flush),
                .i_valid(tile_accept[c] && !tile_drop[c]),
                .o_ready(tx_ready[c]),
                .i_data(tx_inputs[c]),
                .o_valid(tx_valid[c]),
                .i_ready(tx_pop[c]),
                .o_data(tx_heads[c]),
                .o_occupancy(o_tx_queue_occupancy[c*TO+:TO]),
                .o_corrupt(),
                .o_occupied(),
                .o_contents()
            );

            assign tx_pop[c] = tx_tail && tx_owner == TXW'(c);
        end

        always_comb begin
            tx_requests = '0;

            for (int c = 0; c < TX; c++) begin
                beat_t head;
                head = tx_heads[c];

                if (tx_valid[c] && enabled_tx[c]) begin
                    if (serializer_open) tx_requests[c] = serializer_owner == TXW'(c);
                    else tx_requests[c] = NOC_FLOW_CONTROL == FLOW_VALID_READY ||
                        (PACKET_CREDIT_RESERVATION == 0 ? credits[head.metadata.vc] != '0 :
                         32'(credits[head.metadata.vc]) >= PACKET_CREDIT_RESERVATION);
                end
            end
        end

        round_robin_arbiter #(
            .NUM_REQUESTERS(TX),
            .HAS_LOCK(0),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_tx_arbiter (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_request(tx_requests),
            .i_eligible({TX{1'b1}}),
            .i_lock({TX{1'b0}}),
            .i_accept(tx_tail),
            .i_flush(flush || !run),
            .o_grant_valid(tx_grant_valid),
            .o_grant_index(tx_owner),
            .o_grant_onehot(),
            .o_grant_lock(),
            .o_grant_accepted(),
            .o_contended(),
            .o_pending(),
            .o_locked(),
            .o_lock_owner(),
            .o_protocol_error(tx_arbiter_error)
        );

        always_comb begin
            beat_t beat;
            logic [TD-1:0] source_data;
            logic [TB-1:0] source_keep;
            logic [FD-1:0] data;
            logic [FB-1:0] keep;
            beat = tx_heads[tx_owner];
            source_data = beat.data;
            source_keep = beat.keep;
            data = '0;
            keep = '0;
            transmitted = '0;
            o_noc_tx_valid = operate && tx_grant_valid === 1'b1 &&
                (NOC_FLOW_CONTROL == FLOW_VALID_READY || credits[beat.metadata.vc] != '0);

            if (o_noc_tx_valid) begin
                transmitted.metadata = beat.metadata;
                transmitted.fragment_index = fragment;
                transmitted.head = fragment == '0;
                transmitted.tail = 32'(fragment) == FLITS_PER_PACKET - 1;

                for (int b = 0; b < FB; b++) begin
                    int source_byte;
                    source_byte = 32'(fragment) * FB + b;

                    if (source_byte < TB) begin
                        data[b*8+:8] = source_data[source_byte*8+:8];
                        keep[b] = source_keep[source_byte];
                    end
                end
            end

            transmitted.data = data;
            transmitted.keep = keep;
            presented_tx = transmitted;
            serializer_next = serializer_bits;

            if (flush || tx_tail) serializer_next = '0;
            else if (tx_transfer) serializer_next = {1'b1, tx_owner, fragment + 1'b1};
        end

        dff #(.WIDTH(TXW + F + 1), .ASYNC_RESET(ASYNC_RESET)) u_serializer (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(flush || tx_transfer),
            .i_d(serializer_next),
            .o_q(serializer_bits)
        );

        // No returned credit is allowed to change a different epoch or exceed
        // configured capacity. A same-VC launch/return preserves its old count.
        always_comb begin
            credit_return = '0;
            credit_error = NI_ERR_NONE;

            if (active && configured && NOC_FLOW_CONTROL == FLOW_CREDIT) begin
                if (i_noc_tx_credit_valid === 1'b1) begin
                    if (^{i_noc_tx_credit_vc, i_noc_tx_credit_epoch} === 1'bx)
                        credit_error = NI_ERR_UNKNOWN;
                    else if (32'(i_noc_tx_credit_vc) >= V) credit_error = NI_ERR_VC;
                    else if (i_noc_tx_credit_epoch != epoch) credit_error = NI_ERR_EPOCH;
                    else if (credits[i_noc_tx_credit_vc] == CW'(CREDITS) &&
                        !(tx_transfer && transmitted.metadata.vc == i_noc_tx_credit_vc))
                        credit_error = NI_ERR_CREDIT;
                    else credit_return[i_noc_tx_credit_vc] = 1'b1;
                end else if (i_noc_tx_credit_valid !== 1'b0) credit_error = NI_ERR_UNKNOWN;
            end
        end

        for (genvar v = 0; v < V; v++) begin : g_credit
            wire launch = tx_transfer && transmitted.metadata.vc == VW'(v);

            if (NOC_FLOW_CONTROL == FLOW_CREDIT) begin : g_enabled
                counter #(
                    .WIDTH(CW),
                    .RESET_VALUE(CW'(CREDITS)),
                    .ASYNC_RESET(ASYNC_RESET)
                ) u_counter (
                    .i_clk(i_clk),
                    .i_rstb(reset_b),
                    .i_enable(active && configured && (launch != credit_return[v])),
                    .i_clear(flush),
                    .i_load(1'b0),
                    .i_direction(launch),
                    .i_load_value({CW{1'b0}}),
                    .o_count(credits[v]),
                    .o_overflow(),
                    .o_underflow(),
                    .o_terminal()
                );
            end else begin : g_disabled
                assign credits[v] = '0;
            end

            assign o_tx_credit_count[v*CW+:CW] = credits[v];
        end

        // Preserve raw flit/parity until dequeue. Stale-epoch flits bypass every
        // current-epoch queue and partial context, including a full receive FIFO.
        always_comb begin
            incoming.data = i_noc_rx_data;
            incoming.keep = i_noc_rx_keep;
            incoming.head = i_noc_rx_head;
            incoming.tail = i_noc_rx_tail;
            incoming.fragment_index = i_noc_rx_fragment_index;
            incoming.metadata.vc = i_noc_rx_vc;
            incoming.metadata.source_node = i_noc_rx_source_node;
            incoming.metadata.source_endpoint = i_noc_rx_source_endpoint;
            incoming.metadata.destination_node = i_noc_rx_destination_node;
            incoming.metadata.destination_endpoint = i_noc_rx_destination_endpoint;
            incoming.metadata.context_id = i_noc_rx_context_id;
            incoming.metadata.message_type = i_noc_rx_message_type;
            incoming.metadata.traffic_class = i_noc_rx_traffic_class;
            incoming.metadata.packet_id = i_noc_rx_packet_id;
            incoming.metadata.stream_last = i_noc_rx_stream_last;
            incoming.metadata.user_metadata = i_noc_rx_user_metadata;
            incoming.metadata.error = i_noc_rx_error;
            incoming.metadata.epoch = i_noc_rx_epoch;
            incoming_known = ^{incoming.keep, incoming.head, incoming.tail,
                incoming.fragment_index, incoming.metadata} !== 1'bx;
            incoming_vc_valid = ^i_noc_rx_vc !== 1'bx && 32'(i_noc_rx_vc) < V;
            incoming_stale = incoming_known && incoming.metadata.epoch != epoch;
            vc_push = '0;
            o_noc_rx_ready = 1'b0;
            rx_accept = 1'b0;
            rx_direct_drop = 1'b0;
            overflow = 1'b0;
            admission_error = NI_ERR_NONE;

            if (operate && !fatal) begin
                if (incoming_vc_valid && incoming_known &&
                    NOC_FLOW_CONTROL == FLOW_VALID_READY)
                    o_noc_rx_ready = incoming_stale || vc_ready[i_noc_rx_vc];
                if (i_noc_rx_valid === 1'b1) begin
                    if (!incoming_known) admission_error = NI_ERR_UNKNOWN;
                    else if (!incoming_vc_valid) admission_error = NI_ERR_VC;
                    else if (incoming_stale) begin
                        rx_accept = 1'b1;
                        rx_direct_drop = 1'b1;
                        admission_error = NI_ERR_EPOCH;
                    end else if (NOC_FLOW_CONTROL == FLOW_CREDIT || o_noc_rx_ready) begin
                        if (vc_ready[i_noc_rx_vc]) begin
                            vc_push[i_noc_rx_vc] = 1'b1;
                            rx_accept = 1'b1;
                        end else begin
                            overflow = 1'b1;
                            rx_direct_drop = 1'b1;
                            admission_error = NI_ERR_RX_OVERFLOW;
                        end
                    end

                    if (NOC_FLOW_CONTROL == FLOW_CREDIT &&
                        (!incoming_known || !incoming_vc_valid)) rx_direct_drop = 1'b1;
                end else if (i_noc_rx_valid !== 1'b0) admission_error = NI_ERR_UNKNOWN;
            end
        end

        for (genvar v = 0; v < V; v++) begin : g_receive
            event_barrier_queue #(
                .WIDTH(FW + 1),
                .DEPTH(VQD),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_queue (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_flush(flush),
                .i_valid(vc_push[v]),
                .o_ready(vc_ready[v]),
                .i_data({i_noc_rx_parity, incoming}),
                .o_valid(vc_valid[v]),
                .i_ready(vc_pop[v]),
                .o_data(vc_heads[v]),
                .o_occupancy(o_rx_vc_occupancy[v*VO+:VO]),
                .o_corrupt(),
                .o_occupied(),
                .o_contents()
            );

            dff #(.WIDTH(RW), .ASYNC_RESET(ASYNC_RESET)) u_control (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(flush || receive_control_enable[v]),
                .i_d(flush ? {RW{1'b0}} : receive_controls_next[v]),
                .o_q(receive_controls[v])
            );

            dff #(.WIDTH(BW)) u_payload (
                .i_clk(i_clk),
                .i_rstb(1'b1),
                .i_enable(receive_payload_enable[v]),
                .i_d(receive_payloads_next[v]),
                .o_q(receive_payloads[v])
            );

            dff #(.WIDTH(V), .ASYNC_RESET(ASYNC_RESET)) u_predecessors (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(flush || complete_predecessors_enable[v]),
                .i_d(flush ? {V{1'b0}} : complete_predecessors_next[v]),
                .o_q(complete_predecessors[v])
            );
        end

        // Packet completion and receive-flit processing are independent. The
        // predecessor masks preserve final-selection order at each endpoint while
        // letting another endpoint progress around a blocked completed packet.
        always_comb begin
            processing_requests = '0;
            completion_requests = '0;

            for (int v = 0; v < V; v++) begin
                receive_control_t control;
                beat_t payload;
                control = receive_controls[v];
                payload = receive_payloads[v];
                processing_requests[v] = operate && vc_valid[v] && !control.complete;

                if (operate && control.complete && complete_predecessors[v] == '0)
                    completion_requests[v] = rx_ready[payload.metadata.destination_endpoint];
            end
        end

        round_robin_arbiter #(
            .NUM_REQUESTERS(V),
            .HAS_LOCK(0),
            .HOLD_PENDING(0),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_receive_arbiter (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_request(processing_requests),
            .i_eligible({V{1'b1}}),
            .i_lock({V{1'b0}}),
            .i_accept(operate && processing_valid === 1'b1),
            .i_flush(flush || !run),
            .o_grant_valid(processing_valid),
            .o_grant_index(processing_vc),
            .o_grant_onehot(),
            .o_grant_lock(),
            .o_grant_accepted(),
            .o_contended(),
            .o_pending(),
            .o_locked(),
            .o_lock_owner(),
            .o_protocol_error(processing_arbiter_error)
        );

        round_robin_arbiter #(
            .NUM_REQUESTERS(V),
            .HAS_LOCK(0),
            .HOLD_PENDING(0),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_completion_arbiter (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_request(completion_requests),
            .i_eligible({V{1'b1}}),
            .i_lock({V{1'b0}}),
            .i_accept(operate && emission_valid === 1'b1),
            .i_flush(flush || !run),
            .o_grant_valid(emission_valid),
            .o_grant_index(emission_vc),
            .o_grant_onehot(),
            .o_grant_lock(),
            .o_grant_accepted(),
            .o_contended(),
            .o_pending(),
            .o_locked(),
            .o_lock_owner(),
            .o_protocol_error(emission_arbiter_error)
        );

        always_comb begin
            emitted_beat = '0;
            rx_push = '0;

            if (operate && emission_valid === 1'b1) begin
                beat_t payload;
                payload = receive_payloads[emission_vc];
                emitted_beat = payload;
                rx_push[payload.metadata.destination_endpoint] = 1'b1;
            end
        end

        for (genvar c = 0; c < RX; c++) begin : g_rx_queue
            event_barrier_queue #(.WIDTH(BW), .DEPTH(RQD), .ASYNC_RESET(ASYNC_RESET)) u_queue (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_flush(flush),
                .i_valid(rx_push[c]),
                .o_ready(rx_ready[c]),
                .i_data(emitted_beat),
                .o_valid(rx_valid[c]),
                .i_ready(rx_pop[c]),
                .o_data(rx_heads[c]),
                .o_occupancy(o_rx_queue_occupancy[c*RO+:RO]),
                .o_corrupt(),
                .o_occupied(),
                .o_contents()
            );

            assign rx_pop[c] = tile_receive[c];
        end

        always_comb begin
            vc_pop = '0;
            receive_control_enable = '0;
            receive_payload_enable = '0;
            completion_created = '0;
            processing_error = NI_ERR_NONE;
            processing_drop = 1'b0;
            processing_parity_error = 1'b0;
            selected_receive = selected_receive_bits[FW-1:0];

            for (int v = 0; v < V; v++) begin
                receive_controls_next[v] = receive_controls[v];
                receive_payloads_next[v] = receive_payloads[v];
            end

            if (operate && emission_valid === 1'b1) begin
                receive_controls_next[emission_vc] = '0;
                receive_control_enable[emission_vc] = 1'b1;
            end

            if (operate && processing_valid === 1'b1) begin
                receive_control_t control;
                receive_control_t next_control;
                beat_t payload;
                logic [TD-1:0] data;
                logic [TB-1:0] keep;
                logic [FD-1:0] flit_data;
                logic [FB-1:0] flit_keep;
                logic starting;
                logic finish;
                logic [NI_ERROR_WIDTH-1:0] error;
                control = receive_controls[processing_vc];
                next_control = control;
                payload = receive_payloads[processing_vc];
                error = NI_ERR_NONE;
                starting = selected_receive.head;
                finish = selected_receive.tail ||
                    32'(selected_receive.fragment_index) >= FLITS_PER_PACKET - 1 ||
                    (!starting && control.open &&
                        32'(control.next_fragment) >= FLITS_PER_PACKET - 1);
                vc_pop[processing_vc] = 1'b1;
                receive_control_enable[processing_vc] = 1'b1;

                if (starting) begin
                    if (control.open) begin
                        processing_drop = 1'b1;
                        processing_error = NI_ERR_FRAGMENT;
                    end
                    next_control = '0;
                    next_control.open = 1'b1;
                    payload = '0;
                    payload.metadata = selected_receive.metadata;
                end

                data = payload.data;
                keep = payload.keep;
                flit_data = selected_receive.data;
                flit_keep = selected_receive.keep;

                if (queued_parity_bad) begin
                    error = NI_ERR_PARITY;
                    processing_parity_error = 1'b1;
                end else if (!control.open && !starting) error = NI_ERR_FRAGMENT;
                else if ((starting && selected_receive.fragment_index != '0) ||
                    (!starting && selected_receive.fragment_index != F'(control.next_fragment)) ||
                    selected_receive.tail !=
                        (32'(selected_receive.fragment_index) == FLITS_PER_PACKET - 1))
                    error = NI_ERR_FRAGMENT;
                else if (selected_receive.metadata.epoch != epoch) error = NI_ERR_EPOCH;
                else if (32'(selected_receive.metadata.traffic_class) >= CLASSES)
                    error = NI_ERR_CLASS;
                else if (selected_receive.metadata.vc != TRAFFIC_CLASS_TO_VC[
                    32'(selected_receive.metadata.traffic_class)*VW+:VW]) error = NI_ERR_VC_MAPPING;
                else if (selected_receive.metadata.destination_node != N'(LOCAL_NODE_ID) ||
                    32'(selected_receive.metadata.destination_endpoint) >= RX)
                    error = NI_ERR_DESTINATION;
                else if (!enabled_rx[selected_receive.metadata.destination_endpoint])
                    error = NI_ERR_DISABLED;
                else if (configuration.context_check &&
                    selected_receive.metadata.context_id != configuration.context_id)
                    error = NI_ERR_CONTEXT;
                else if (!starting && selected_receive.metadata != payload.metadata)
                    error = NI_ERR_SIDEBAND;

                for (int b = 0; b < FB; b++) begin
                    int tile_byte;
                    tile_byte = 32'(selected_receive.fragment_index) * FB + b;

                    if (tile_byte >= TB) begin
                        if ({flit_keep[b], flit_data[b*8+:8]} !== '0 &&
                            error == NI_ERR_NONE) error = NI_ERR_PADDING;
                    end else if ((control.open || starting) && !next_control.bad) begin
                        keep[tile_byte] = flit_keep[b];
                        data[tile_byte*8+:8] = flit_keep[b] ?
                            flit_data[b*8+:8] : 8'b0;
                    end
                end

                payload.data = data;
                payload.keep = keep;

                if (finish && payload.keep == '0 && error == NI_ERR_NONE) error = NI_ERR_KEEP;

                if (processing_error == NI_ERR_NONE) processing_error = error;

                if (control.open || starting) begin
                    next_control.bad |= error != NI_ERR_NONE;
                    next_control.next_fragment = starting ? (F + 1)'(1) :
                        control.next_fragment + 1'b1;

                    if (finish) begin
                        next_control.open = 1'b0;

                        if (next_control.bad) begin
                            next_control = '0;
                            processing_drop = 1'b1;
                        end else begin
                            next_control.complete = 1'b1;
                            next_control.next_fragment = '0;
                            completion_created[processing_vc] = 1'b1;
                        end
                    end

                    receive_payloads_next[processing_vc] = payload;
                    receive_payload_enable[processing_vc] = !control.bad || starting;
                end else begin
                    next_control = '0;
                    processing_drop = 1'b1;
                end

                receive_controls_next[processing_vc] = next_control;
            end
        end

        always_comb begin
            for (int v = 0; v < V; v++) begin
                logic [V-1:0] predecessors;
                beat_t created;
                predecessors = complete_predecessors[v];
                created = receive_payloads_next[v];

                if (operate && emission_valid === 1'b1) predecessors[emission_vc] = 1'b0;

                if (completion_created[v]) begin
                    predecessors = '0;

                    for (int older = 0; older < V; older++) begin
                        receive_control_t control;
                        beat_t payload;
                        control = receive_controls[older];
                        payload = receive_payloads[older];

                        if (control.complete && payload.metadata.destination_endpoint ==
                            created.metadata.destination_endpoint &&
                            !(emission_valid && emission_vc == VW'(older)))
                            predecessors[older] = 1'b1;
                    end
                end

                complete_predecessors_next[v] = predecessors;
                complete_predecessors_enable[v] = operate &&
                    (completion_created[v] || predecessors != complete_predecessors[v]);
            end
        end

        always_comb begin
            o_tile_rx_valid = '0;
            o_tile_rx_data = '0;
            o_tile_rx_keep = '0;
            o_tile_rx_last = '0;
            o_tile_rx_source_node = '0;
            o_tile_rx_source_endpoint = '0;
            o_tile_rx_context_id = '0;
            o_tile_rx_message_type = '0;
            o_tile_rx_traffic_class = '0;
            o_tile_rx_packet_id = '0;
            o_tile_rx_user_metadata = '0;
            o_tile_rx_error = '0;
            tile_receive = '0;
            receive_stall = '0;

            for (int c = 0; c < RX; c++) begin
                beat_t beat;
                beat = rx_heads[c];

                if (operate && rx_valid[c]) begin
                    o_tile_rx_valid[c] = 1'b1;
                    o_tile_rx_data[c*TD+:TD] = beat.data;
                    o_tile_rx_keep[c*TB+:TB] = beat.keep;
                    o_tile_rx_last[c] = beat.metadata.stream_last;
                    o_tile_rx_source_node[c*N+:N] = beat.metadata.source_node;
                    o_tile_rx_source_endpoint[c*EP+:EP] = beat.metadata.source_endpoint;
                    o_tile_rx_context_id[c*CX+:CX] = beat.metadata.context_id;
                    o_tile_rx_message_type[c*MT+:MT] = beat.metadata.message_type;
                    o_tile_rx_traffic_class[c*TC+:TC] = beat.metadata.traffic_class;
                    o_tile_rx_packet_id[c*PI+:PI] = beat.metadata.packet_id;
                    o_tile_rx_user_metadata[c*U+:U] = beat.metadata.user_metadata;
                    o_tile_rx_error[c*ER+:ER] = beat.metadata.error;
                    tile_receive[c] = i_tile_rx_ready[c] === 1'b1;
                    receive_stall[c] = i_tile_rx_ready[c] === 1'b0;
                end
            end
        end

        if (ENABLE_LINK_PARITY == 1) begin : g_link_parity
            wire receive_parity;
            wire queued_parity;
            wire [FW-1:0] unused_receive;
            wire [FW-1:0] unused_queued;
            wire unused_error;

            parity #(.DATA_WIDTH(FW), .PARITY_GRANULE_WIDTH(FW)) u_link (
                .i_generate_data(transmitted),
                .o_generated_parity(tx_parity),
                .i_check_data(incoming),
                .i_check_parity(i_noc_rx_parity),
                .o_checked_data(unused_receive),
                .o_error_vector(receive_parity),
                .o_granule_valid(),
                .o_no_error(),
                .o_any_error(unused_error)
            );

            parity #(.DATA_WIDTH(FW), .PARITY_GRANULE_WIDTH(FW)) u_queued (
                .i_generate_data({FW{1'b0}}),
                .o_generated_parity(),
                .i_check_data(selected_receive_bits[FW-1:0]),
                .i_check_parity(selected_receive_bits[FW]),
                .o_checked_data(unused_queued),
                .o_error_vector(queued_parity),
                .o_granule_valid(),
                .o_no_error(),
                .o_any_error()
            );

            assign incoming_parity_bad = receive_parity !== 1'b0;
            assign queued_parity_bad = queued_parity !== 1'b0;
        end else begin : g_no_link_parity
            assign tx_parity = 1'b0;
            assign incoming_parity_bad = 1'b0;
            assign queued_parity_bad = 1'b0;
        end
        assign o_noc_tx_data = transmitted.data;
        assign o_noc_tx_keep = transmitted.keep;
        assign o_noc_tx_head = transmitted.head;
        assign o_noc_tx_tail = transmitted.tail;
        assign o_noc_tx_fragment_index = transmitted.fragment_index;
        assign o_noc_tx_vc = transmitted.metadata.vc;
        assign o_noc_tx_source_node = transmitted.metadata.source_node;
        assign o_noc_tx_source_endpoint = transmitted.metadata.source_endpoint;
        assign o_noc_tx_destination_node = transmitted.metadata.destination_node;
        assign o_noc_tx_destination_endpoint = transmitted.metadata.destination_endpoint;
        assign o_noc_tx_context_id = transmitted.metadata.context_id;
        assign o_noc_tx_message_type = transmitted.metadata.message_type;
        assign o_noc_tx_traffic_class = transmitted.metadata.traffic_class;
        assign o_noc_tx_packet_id = transmitted.metadata.packet_id;
        assign o_noc_tx_stream_last = transmitted.metadata.stream_last;
        assign o_noc_tx_user_metadata = transmitted.metadata.user_metadata;
        assign o_noc_tx_error = transmitted.metadata.error;
        assign o_noc_tx_epoch = transmitted.metadata.epoch;
        assign o_noc_tx_parity = o_noc_tx_valid ? tx_parity : 1'b0;

        always_comb begin
            detected_error = NI_ERR_NONE;

            if (run) begin
                if (!global_known) detected_error = NI_ERR_UNKNOWN;
                else if (configuration_bad) detected_error = NI_ERR_CONFIG;
                else if (credit_error != NI_ERR_NONE) detected_error = credit_error;
                else if (admission_error != NI_ERR_NONE) detected_error = admission_error;
                else if (processing_error != NI_ERR_NONE) detected_error = processing_error;
                else if (tx_arbiter_error || processing_arbiter_error || emission_arbiter_error)
                    detected_error = NI_ERR_FRAGMENT;

                for (int c = 0; c < TX; c++) begin
                    if (detected_error == NI_ERR_NONE && tile_drop[c])
                        detected_error = tx_errors[c];
                    if (operate && i_tile_tx_valid[c] !== 1'b0 &&
                        i_tile_tx_valid[c] !== 1'b1 && detected_error == NI_ERR_NONE)
                        detected_error = NI_ERR_UNKNOWN;
                end

                if (operate && ((NOC_FLOW_CONTROL == FLOW_VALID_READY && o_noc_tx_valid &&
                    i_noc_tx_ready !== 1'b0 && i_noc_tx_ready !== 1'b1) ||
                    ((^i_tile_rx_ready === 1'bx) && (|o_tile_rx_valid))) &&
                    detected_error == NI_ERR_NONE) detected_error = NI_ERR_UNKNOWN;
            end
        end

        wire clear_error = o_quiescent && !configuration_accept &&
            i_error_clear === 1'b1 && detected_error == NI_ERR_NONE;

        dff #(.WIDTH(NI_ERROR_WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && (clear_error || (!o_error && detected_error != NI_ERR_NONE))),
            .i_d(clear_error ? {NI_ERROR_WIDTH{1'b0}} : detected_error),
            .o_q(sticky_error)
        );

        dff #(.ASYNC_RESET(ASYNC_RESET)) u_fatal (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(flush || overflow),
            .i_d(!flush),
            .o_q(fatal)
        );

        assign next_events = {configuration_good, configuration_bad, flush && !o_idle,
                tile_accept, tile_receive, tx_transfer, rx_accept, tile_stall,
                receive_stall, tile_drop, processing_drop || rx_direct_drop,
                processing_parity_error || (rx_direct_drop && incoming_parity_bad),
                NOC_FLOW_CONTROL == FLOW_CREDIT && (|vc_pop),
                NOC_FLOW_CONTROL == FLOW_CREDIT && (|vc_pop) ? processing_vc : {VW{1'b0}},
                NOC_FLOW_CONTROL == FLOW_CREDIT && (|vc_pop) ?
                    E'(selected_receive.metadata.epoch) : {E{1'b0}}};

        dff #(.WIDTH(EVENT_BITS), .ASYNC_RESET(ASYNC_RESET)) u_events (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && (|{events, next_events})),
            .i_d(next_events),
            .o_q(events)
        );

        assign {o_config_accepted, o_config_rejected, o_flushed,
            o_event_tile_tx_accept, o_event_tile_rx_transfer, o_event_noc_tx_transfer,
            o_event_noc_rx_accept, o_event_tx_stall, o_event_rx_stall, o_event_tx_drop,
            o_event_rx_drop, o_event_parity_error, o_noc_rx_credit_valid,
            o_noc_rx_credit_vc, o_noc_rx_credit_epoch} = run ? events : '0;
    end
endmodule
`default_nettype wire
