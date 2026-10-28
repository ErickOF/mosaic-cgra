`timescale 1ns / 1ps

// Buffered five-port wormhole router. Packet framing is tracked at ingress;
// output reservations outlive FIFO pops and release only on external tail transfer.
module noc_router #(
    parameter MESH_X = 4,
    parameter MESH_Y = 4,
    parameter ROUTER_X = 0,
    parameter ROUTER_Y = 0,
    parameter FLIT_DATA_WIDTH = 32,
    parameter NUM_VCS = 2,
    parameter INPUT_VC_DEPTH = 2,
    parameter FLOW_CONTROL = 1,
    parameter OUTPUT_INITIAL_CREDITS = 2,
    // Zero preserves wormhole admission. A fixed-envelope fabric may require
    // complete downstream packet capacity before acquiring any input/output lock.
    parameter PACKET_CREDIT_RESERVATION = 0,
    parameter ROUTING_ALGORITHM = 0,
    parameter NUM_TRAFFIC_CLASSES = 8,
    parameter ENABLE_QOS = 1,
    parameter HIGH_SERVICE_BURST_LIMIT = 8,
    parameter NODE_ID_WIDTH = 8,
    parameter ENDPOINT_ID_WIDTH = 4,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter MESSAGE_TYPE_WIDTH = 4,
    parameter TRAFFIC_CLASS_WIDTH = 3,
    parameter PACKET_ID_WIDTH = 8,
    parameter FRAGMENT_INDEX_WIDTH = 4,
    parameter USER_METADATA_WIDTH = 16,
    parameter ERROR_WIDTH = 4,
    parameter LINK_EPOCH_WIDTH = 2,
    parameter ENABLE_LINK_PARITY = 0,
    parameter BUFFER_PROTECTION = 0,
    parameter OUTPUT_PIPELINE = 1,
    parameter ASYNC_RESET = 0,
    localparam bit GEOMETRY_VALID =
        ((PACKET_CREDIT_RESERVATION >= 0 &&
            PACKET_CREDIT_RESERVATION <= OUTPUT_INITIAL_CREDITS) === 1'b1) &&
        (^PACKET_CREDIT_RESERVATION !== 1'bx) &&
        ((MESH_X >= 1) === 1'b1) && ( ^ MESH_X !== 1'bx) &&
        ((MESH_Y >= 1) === 1'b1) && ( ^ MESH_Y !== 1'bx) &&
        ((FLIT_DATA_WIDTH >= 1) === 1'b1) && ( ^ FLIT_DATA_WIDTH !== 1'bx) &&
        ((64'(MESH_X) < 64'd2147483647) === 1'b1) &&
        ((64'(MESH_Y) < 64'd2147483647) === 1'b1) &&
        ((64'(FLIT_DATA_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(NUM_VCS) < 64'd2147483647) === 1'b1) &&
        ((64'(INPUT_VC_DEPTH) < 64'd2147483647) === 1'b1) &&
        ((64'(OUTPUT_INITIAL_CREDITS) < 64'd2147483647) === 1'b1) &&
        ((64'(NUM_TRAFFIC_CLASSES) < 64'd2147483647) === 1'b1) &&
        ((64'(NODE_ID_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(ENDPOINT_ID_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(CONTEXT_ID_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(MESSAGE_TYPE_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(TRAFFIC_CLASS_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(PACKET_ID_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(FRAGMENT_INDEX_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(USER_METADATA_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(ERROR_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(LINK_EPOCH_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(HIGH_SERVICE_BURST_LIMIT) < 64'd2147483647) === 1'b1) &&
        ((NUM_VCS >= 1) === 1'b1) && ( ^ NUM_VCS !== 1'bx) &&
        ((INPUT_VC_DEPTH >= 1) === 1'b1) && ( ^ INPUT_VC_DEPTH !== 1'bx) &&
        ((OUTPUT_INITIAL_CREDITS >= 1) === 1'b1) && ( ^ OUTPUT_INITIAL_CREDITS !== 1'bx) &&
        ((NUM_TRAFFIC_CLASSES >= 1) === 1'b1) && ( ^ NUM_TRAFFIC_CLASSES !== 1'bx) &&
        (((HIGH_SERVICE_BURST_LIMIT >= 1) ||
            (ENABLE_QOS == 0 && HIGH_SERVICE_BURST_LIMIT == 0)) === 1'b1) &&
            ( ^ HIGH_SERVICE_BURST_LIMIT !== 1'bx) &&
        ((NODE_ID_WIDTH >= 1) === 1'b1) && ( ^ NODE_ID_WIDTH !== 1'bx) &&
        ((ENDPOINT_ID_WIDTH >= 1) === 1'b1) && ( ^ ENDPOINT_ID_WIDTH !== 1'bx) &&
        ((CONTEXT_ID_WIDTH >= 1) === 1'b1) && ( ^ CONTEXT_ID_WIDTH !== 1'bx) &&
        ((MESSAGE_TYPE_WIDTH >= 1) === 1'b1) && ( ^ MESSAGE_TYPE_WIDTH !== 1'bx) &&
        ((TRAFFIC_CLASS_WIDTH >= 1) === 1'b1) && ( ^ TRAFFIC_CLASS_WIDTH !== 1'bx) &&
        ((PACKET_ID_WIDTH >= 1) === 1'b1) && ( ^ PACKET_ID_WIDTH !== 1'bx) &&
        ((FRAGMENT_INDEX_WIDTH >= 1) === 1'b1) && ( ^ FRAGMENT_INDEX_WIDTH !== 1'bx) &&
        ((USER_METADATA_WIDTH >= 1) === 1'b1) && ( ^ USER_METADATA_WIDTH !== 1'bx) &&
        ((ERROR_WIDTH >= 1) === 1'b1) && ( ^ ERROR_WIDTH !== 1'bx) &&
        ((LINK_EPOCH_WIDTH >= 1) === 1'b1) && ( ^ LINK_EPOCH_WIDTH !== 1'bx) &&
        ((ROUTER_X >= 0 && ROUTER_X < MESH_X) === 1'b1) && ( ^ ROUTER_X !== 1'bx) &&
        ((ROUTER_Y >= 0 && ROUTER_Y < MESH_Y) === 1'b1) && ( ^ ROUTER_Y !== 1'bx) &&
        ((FLOW_CONTROL === 0) || (FLOW_CONTROL === 1)) &&
        ((ROUTING_ALGORITHM === 0) || (ROUTING_ALGORITHM === 1)) &&
        ((ENABLE_QOS === 0) || (ENABLE_QOS === 1)) &&
        ((ENABLE_LINK_PARITY === 0) || (ENABLE_LINK_PARITY === 1)) &&
        ((OUTPUT_PIPELINE === 0) || (OUTPUT_PIPELINE === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((BUFFER_PROTECTION === 0) || (BUFFER_PROTECTION === 1) || (BUFFER_PROTECTION === 2)) &&
        ((FLIT_DATA_WIDTH % 8 == 0) === 1'b1) &&
        ((FLOW_CONTROL != 1 || LINK_EPOCH_WIDTH >= 2) === 1'b1) &&
        ((64'(MESH_X) * 64'(MESH_Y) < 64'd2147483647) === 1'b1) &&
        ((64'(NUM_TRAFFIC_CLASSES) * (64'(NUM_VCS) + 1) < 64'd2147483647) === 1'b1) &&
        ((NODE_ID_WIDTH >= 32 || 64'(MESH_X) * 64'(MESH_Y) < (64'd1 << NODE_ID_WIDTH)) === 1'b1) &&
        ((TRAFFIC_CLASS_WIDTH >= 32 ||
            64'(NUM_TRAFFIC_CLASSES) <= (64'd1 << TRAFFIC_CLASS_WIDTH)) === 1'b1) &&
        ((128'(NUM_VCS) * 128'(INPUT_VC_DEPTH) * (128'(FLIT_DATA_WIDTH) +
            128'(NODE_ID_WIDTH) * 2 + 128'(ENDPOINT_ID_WIDTH) * 2 + 128'(CONTEXT_ID_WIDTH) +
            128'(MESSAGE_TYPE_WIDTH) + 128'(TRAFFIC_CLASS_WIDTH) + 128'(PACKET_ID_WIDTH) +
            128'(FRAGMENT_INDEX_WIDTH) + 128'(USER_METADATA_WIDTH) + 128'(ERROR_WIDTH) +
            128'(LINK_EPOCH_WIDTH) + 128'(FLIT_DATA_WIDTH) / 8 + 128'(NUM_VCS) + 16) * 32 <
            128'd2147483647) === 1'b1),
    localparam int V = GEOMETRY_VALID ? NUM_VCS : 1,
    localparam int D = GEOMETRY_VALID ? FLIT_DATA_WIDTH : 8,
    localparam int N = GEOMETRY_VALID ? NODE_ID_WIDTH : 1,
    localparam int EP = GEOMETRY_VALID ? ENDPOINT_ID_WIDTH : 1,
    localparam int CX = GEOMETRY_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int MT = GEOMETRY_VALID ? MESSAGE_TYPE_WIDTH : 1,
    localparam int TC = GEOMETRY_VALID ? TRAFFIC_CLASS_WIDTH : 1,
    localparam int PI = GEOMETRY_VALID ? PACKET_ID_WIDTH : 1,
    localparam int F = GEOMETRY_VALID ? FRAGMENT_INDEX_WIDTH : 1,
    localparam int U = GEOMETRY_VALID ? USER_METADATA_WIDTH : 1,
    localparam int ER = GEOMETRY_VALID ? ERROR_WIDTH : 1,
    localparam int E = GEOMETRY_VALID ? LINK_EPOCH_WIDTH : 2,
    localparam int CLASSES = GEOMETRY_VALID ? NUM_TRAFFIC_CLASSES : 1,
    localparam int DEPTH = GEOMETRY_VALID ? INPUT_VC_DEPTH : 1,
    localparam int CREDITS = GEOMETRY_VALID ? OUTPUT_INITIAL_CREDITS : 1,
    localparam int VW = V > 1 ? $clog2(V) : 1,
    parameter [CLASSES*VW-1:0] TRAFFIC_CLASS_TO_VC = default_vc_map(),
    parameter [CLASSES-1:0] TRAFFIC_CLASS_TO_SERVICE = default_service_map(),
    localparam bit PARAMETERS_VALID = GEOMETRY_VALID && maps_valid(),
    localparam int NUM_PORTS = 5,
    localparam int PORT_WIDTH = 3,
    localparam int K = D / 8,
    localparam int COUNT = NUM_PORTS * V,
    localparam int OCC = $clog2(DEPTH + 1),
    localparam int CW = $clog2(CREDITS + 1)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_drain,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_config_valid,
    output logic o_config_ready,
    input logic [4:0] i_config_port_enable,
    input logic [4:0] i_config_fault_port_mask,
    output logic o_config_accepted,
    output logic o_config_rejected,
    input logic [4:0] i_in_valid,
    output logic [4:0] o_in_ready,
    input logic [5*D-1:0] i_in_data,
    input logic [5*K-1:0] i_in_keep,
    input logic [4:0] i_in_head,
    input logic [4:0] i_in_tail,
    input logic [5*F-1:0] i_in_fragment_index,
    input logic [5*VW-1:0] i_in_vc,
    input logic [5*N-1:0] i_in_source_node,
    input logic [5*EP-1:0] i_in_source_endpoint,
    input logic [5*N-1:0] i_in_destination_node,
    input logic [5*EP-1:0] i_in_destination_endpoint,
    input logic [5*CX-1:0] i_in_context_id,
    input logic [5*MT-1:0] i_in_message_type,
    input logic [5*TC-1:0] i_in_traffic_class,
    input logic [5*PI-1:0] i_in_packet_id,
    input logic [4:0] i_in_stream_last,
    input logic [5*U-1:0] i_in_user_metadata,
    input logic [5*ER-1:0] i_in_error,
    input logic [5*E-1:0] i_in_epoch,
    input logic [4:0] i_in_parity,
    output logic [4:0] o_out_valid,
    input logic [4:0] i_out_ready,
    output logic [5*D-1:0] o_out_data,
    output logic [5*K-1:0] o_out_keep,
    output logic [4:0] o_out_head,
    output logic [4:0] o_out_tail,
    output logic [5*F-1:0] o_out_fragment_index,
    output logic [5*VW-1:0] o_out_vc,
    output logic [5*N-1:0] o_out_source_node,
    output logic [5*EP-1:0] o_out_source_endpoint,
    output logic [5*N-1:0] o_out_destination_node,
    output logic [5*EP-1:0] o_out_destination_endpoint,
    output logic [5*CX-1:0] o_out_context_id,
    output logic [5*MT-1:0] o_out_message_type,
    output logic [5*TC-1:0] o_out_traffic_class,
    output logic [5*PI-1:0] o_out_packet_id,
    output logic [4:0] o_out_stream_last,
    output logic [5*U-1:0] o_out_user_metadata,
    output logic [5*ER-1:0] o_out_error,
    output logic [5*E-1:0] o_out_epoch,
    output logic [4:0] o_out_parity,
    input logic [4:0] i_out_credit_valid,
    input logic [5*VW-1:0] i_out_credit_vc,
    input logic [5*E-1:0] i_out_credit_epoch,
    output logic [4:0] o_in_credit_valid,
    output logic [5*VW-1:0] o_in_credit_vc,
    output logic [5*E-1:0] o_in_credit_epoch,
    output logic [4:0] o_active_port_enable,
    output logic [4:0] o_active_fault_port_mask,
    output logic [5*E-1:0] o_link_epoch,
    output logic [COUNT*OCC-1:0] o_input_vc_occupancy,
    output logic [COUNT*CW-1:0] o_output_credit_count,
    output logic [4:0] o_input_packet_locked,
    output logic [4:0] o_output_packet_locked,
    output logic o_idle,
    output logic o_quiescent,
    output logic o_drain_done,
    output logic o_flushed,
    output logic o_error,
    output logic [4:0] o_error_code,
    output logic o_fatal_error,
    output logic [4:0] o_event_input_accept,
    output logic [4:0] o_event_output_transfer,
    output logic [4:0] o_event_packet_head,
    output logic [4:0] o_event_packet_tail,
    output logic [4:0] o_event_input_stall,
    output logic [4:0] o_event_output_stall,
    output logic [4:0] o_event_vc_starved,
    output logic [4:0] o_event_credit_starved,
    output logic [4:0] o_event_route_error,
    output logic [4:0] o_event_protocol_error,
    output logic [4:0] o_event_parity_error,
    output logic [4:0] o_event_buffer_corrected,
    output logic [4:0] o_event_buffer_uncorrectable
);
    import noc_router_pkg::*;

    function automatic logic [CLASSES*VW-1:0] default_vc_map();
        logic [CLASSES*VW-1:0] result;
        result = '0;

        for (int c = 0; c < CLASSES; c++) result[c*VW+:VW] = VW'(c % V);
        return result;
    endfunction

    function automatic logic [CLASSES-1:0] default_service_map();
        logic [CLASSES-1:0] result;

        for (int c = 0; c < CLASSES; c++) result[c] = 1'(c % 2);
        return result;
    endfunction

    function automatic bit maps_valid();
        bit legal;
        legal = ( ^ {TRAFFIC_CLASS_TO_VC, TRAFFIC_CLASS_TO_SERVICE} !== 1'bx);

        for (int c = 0; c < CLASSES; c++)
            if (32'(TRAFFIC_CLASS_TO_VC[c*VW+:VW]) >= V) legal = 1'b0;
        return legal;
    endfunction

    localparam int QW = GEOMETRY_VALID && HIGH_SERVICE_BURST_LIMIT > 0 ?
            $clog2(64'(HIGH_SERVICE_BURST_LIMIT) + 1) : 1;
    // The unused QoS cone gets a positive bound even when the feature is disabled.
    localparam int SERVICE_LIMIT = GEOMETRY_VALID && ENABLE_QOS == 1 ?
        HIGH_SERVICE_BURST_LIMIT : 1;
    localparam int NODE_COUNT = MESH_X * MESH_Y;
    localparam int LOCAL_NODE = ROUTER_Y * MESH_X + ROUTER_X;

    // Record layouts depend on this instance's widths; encodings live in the package.
    typedef struct packed {
        logic [D-1:0] data;
        logic [K-1:0] keep;
        logic head;
        logic tail;
        logic [F-1:0] fragment_index;
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
        logic discard;
    } flit_t;

    localparam int FW = $bits(flit_t);

    typedef struct packed {
        logic open;
        logic quarantine;
        logic bad;
        logic [F:0] next_fragment;
        logic [FW-1:0] invariant;
    } ingress_t;

    typedef struct packed {
        logic [E-1:0] epoch;
        logic input_locked;
        logic [VW-1:0] input_vc;
        logic [PORT_WIDTH-1:0] route;
        logic output_locked;
        logic [2:0] owner;
        logic [VW-1:0] output_vc;
        logic pending;
        logic [2:0] pending_owner;
        logic [VW-1:0] pending_vc;
        logic pending_high;
        logic [QW-1:0] high_budget;
    } port_state_t;

    typedef struct packed {
        logic error;
        logic fatal;
        logic [4:0] code;
    } error_state_t;

    function automatic logic [FW-1:0] ownership_mask();
        /* verilator lint_off UNUSEDSIGNAL */
        flit_t mask;
        /* verilator lint_on UNUSEDSIGNAL */
        mask = '1;
        mask.data = '0;
        mask.keep = '0;
        mask.error = '0;
        return mask;
    endfunction

    function automatic logic [FW-1:0] invariant_mask();
        /* verilator lint_off UNUSEDSIGNAL */
        flit_t mask;
        /* verilator lint_on UNUSEDSIGNAL */
        mask = ownership_mask();
        mask.head = '0;
        mask.tail = '0;
        mask.fragment_index = '0;
        mask.discard = '0;
        return mask;
    endfunction

    localparam logic [FW-1:0] OWN_MASK = ownership_mask();
    localparam logic [FW-1:0] INV_MASK = invariant_mask();

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        noc_router_parameters_must_be_valid invalid_parameters ();
    end else begin : g_router
        // Division and remainder use static mesh dimensions, never flit-sized divisors.
        function automatic int route(input logic [N-1:0] destination);
            int x;
            int y;
            x = int'(destination) % MESH_X;
            y = int'(destination) / MESH_X;

            if (destination >= N'(NODE_COUNT)) return 5;
            if (destination == N'(LOCAL_NODE)) return int'(PORT_LOCAL);
            if (ROUTING_ALGORITHM == 32'(ROUTE_XY)) begin
                if (x > ROUTER_X) return int'(PORT_EAST);
                if (x < ROUTER_X) return int'(PORT_WEST);
                if (y > ROUTER_Y) return int'(PORT_SOUTH);
                if (y < ROUTER_Y) return int'(PORT_NORTH);
            end else begin
                if (y > ROUTER_Y) return int'(PORT_SOUTH);
                if (y < ROUTER_Y) return int'(PORT_NORTH);
                if (x > ROUTER_X) return int'(PORT_EAST);
                if (x < ROUTER_X) return int'(PORT_WEST);
            end

            return int'(PORT_LOCAL);
        endfunction

        function automatic logic class_legal(input logic [TC-1:0] value);
            return {1'b0, value} < (TC + 1)'(CLASSES);
        endfunction

        function automatic bit credit_out_of_range(input logic [CW:0] value);
            return value > (CW + 1)'(CREDITS);
        endfunction

        function automatic bit cardinal_legal(input int port_index);
            case (port_index)
                1: return ROUTER_Y > 0;
                2: return ROUTER_X < MESH_X - 1;
                3: return ROUTER_Y < MESH_Y - 1;
                4: return ROUTER_X > 0;
                default: return 1'b1;
            endcase
        endfunction

        wire [FW-1:0] incoming[5];
        wire [FW-1:0] queue_head[COUNT];
        logic [FW-1:0] queue_input[COUNT];
        wire [COUNT-1:0] queue_valid;
        wire [COUNT-1:0] queue_ready;
        logic [COUNT-1:0] queue_push;
        logic [COUNT-1:0] queue_pop;
        wire [COUNT-1:0] queue_corrected;
        wire [COUNT-1:0] queue_bad;
        wire [COUNT-1:0] queue_ownership_bad;
        wire [COUNT-1:0] frame_corrupt;
        wire [COUNT-1:0] discard_corrupt;
        wire [COUNT-1:0] discarding;
        logic [COUNT-1:0] discard_next;
        wire [$bits(ingress_t)-1:0] frame[COUNT];
        logic [$bits(ingress_t)-1:0] frame_next[COUNT];
        wire [$bits(port_state_t)-1:0] port_state[5];
        logic [$bits(port_state_t)-1:0] port_next[5];
        wire [4:0] port_corrupt;
        wire [4:0] pipe_corrupt;
        wire [4:0] snapshot_corrupt;
        wire [FW-1:0] pipe_data[5];
        wire [FW-1:0] snapshot[5];
        logic [FW-1:0] snapshot_next[5];
        logic [4:0] snapshot_enable;
        wire [4:0] pipe_valid;
        wire [4:0] unused_pipe_ready;
        // Partial profile: these holding-stage inputs are unused when PIPELINE=0.
        /* verilator lint_off UNUSEDSIGNAL */
        logic [FW-1:0] pipe_input[5];
        /* verilator lint_on UNUSEDSIGNAL */
        logic [4:0] pipe_push;
        logic [4:0] pipe_pop;
        logic [4:0] link_transfer;
        logic [FW-1:0] outgoing[5];
        wire [CW-1:0] credits[COUNT];
        logic [COUNT-1:0] credit_return;
        logic [COUNT-1:0] credit_launch;
        wire [4:0] installed_enable;
        wire [4:0] installed_fault;
        wire configuration_corrupt;
        wire [4:0] usable = installed_enable & ~ installed_fault;
        wire [$bits(error_state_t)-1:0] errors;
        logic [$bits(error_state_t)-1:0] error_next;
        wire errors_corrupt;
        logic idle;
        logic running;
        logic live_fatal;
        logic unknown_control;
        logic fault_event;
        logic configuration_legal;
        logic [4:0] detected_error;
        logic [4:0] accepted_input;
        logic [4:0] sink_input;
        logic [4:0] input_stall;
        logic [4:0] output_stall;
        logic [4:0] vc_starved;
        logic [4:0] credit_starved;
        logic [4:0] route_error;
        logic [4:0] protocol_error;
        logic [4:0] parity_error;
        logic [4:0] buffer_corrected;
        logic [4:0] buffer_bad;
        logic [4:0] head_event;
        logic [4:0] tail_event;
        logic [4:0] input_credit;
        logic [5*VW-1:0] input_credit_vc;
        logic [5*E-1:0] input_credit_epoch;
        logic [4:0] input_candidate_valid;
        logic [4:0] input_candidate_drop;
        logic [VW-1:0] input_candidate_vc[5];
        logic [2:0] input_route[5];
        logic [FW-1:0] input_flit[5];
        logic [4:0] input_high;
        logic [V-1:0] input_requests[5];
        wire [4:0] input_grant_valid;
        wire [VW-1:0] input_grant[5];
        logic [4:0] input_accept;
        logic [4:0] normal_requests[5];
        logic [4:0] normal_waiting;
        logic [4:0] high_requests[5];
        wire [4:0] normal_valid;
        wire [4:0] high_valid;
        wire [2:0] normal_grant[5];
        wire [2:0] high_grant[5];
        logic [4:0] normal_accept;
        logic [4:0] high_accept;
        wire [14:0] arbiter_error;
        logic [4:0] switch_fire;
        logic [2:0] selected_owner[5];
        logic [VW-1:0] selected_vc[5];
        logic [4:0] selected_valid;
        logic [4:0] selected_high;
        logic [FW-1:0] selected_flit[5];
        wire flush = i_flush === 1'b1;
        wire configure = i_config_valid === 1'b1 && o_config_ready;
        wire state_clear = flush;
        error_state_t error_value;
        assign error_value = errors;
        assign o_error = error_value.error;
        assign o_error_code = error_value.code;
        assign o_fatal_error = error_value.fatal;
        assign o_active_port_enable = installed_enable;
        assign o_active_fault_port_mask = installed_fault;
        assign o_idle = idle;
        assign o_drain_done = (i_drain === 1'b1) && idle;
        assign o_config_ready = (i_rstb === 1'b1) && idle && (i_flush === 1'b0) &&
            (i_drain === 1'b0) && (i_error_clear === 1'b0);
        assign o_quiescent = o_config_ready && (i_config_valid === 1'b0) &&
            !(|accepted_input) && !(|link_transfer) && !(|credit_return);

        for (genvar p = 0; p < 5; p++) begin : g_port
            assign incoming[p] = {
                i_in_data[p*D+:D],
                i_in_keep[p*K+:K],
                i_in_head[p],
                i_in_tail[p],
                i_in_fragment_index[p*F+:F],
                i_in_vc[p*VW+:VW],
                i_in_source_node[p*N+:N],
                i_in_source_endpoint[p*EP+:EP],
                i_in_destination_node[p*N+:N],
                i_in_destination_endpoint[p*EP+:EP],
                i_in_context_id[p*CX+:CX],
                i_in_message_type[p*MT+:MT],
                i_in_traffic_class[p*TC+:TC],
                i_in_packet_id[p*PI+:PI],
                i_in_stream_last[p],
                i_in_user_metadata[p*U+:U],
                i_in_error[p*ER+:ER],
                i_in_epoch[p*E+:E],
                1'b0
            };

            wire [FW-1:0] visible = o_out_valid[p] ? outgoing[p] : '0;
            /* verilator lint_off UNUSEDSIGNAL */
            flit_t output_flit;
            /* verilator lint_on UNUSEDSIGNAL */
            assign output_flit = visible;
            assign o_out_data[p*D+:D] = output_flit.data;
            assign o_out_keep[p*K+:K] = output_flit.keep;
            assign o_out_head[p] = output_flit.head;
            assign o_out_tail[p] = output_flit.tail;
            assign o_out_fragment_index[p*F+:F] = output_flit.fragment_index;
            assign o_out_vc[p*VW+:VW] = output_flit.vc;
            assign o_out_source_node[p*N+:N] = output_flit.source_node;
            assign o_out_source_endpoint[p*EP+:EP] = output_flit.source_endpoint;
            assign o_out_destination_node[p*N+:N] = output_flit.destination_node;
            assign o_out_destination_endpoint[p*EP+:EP] = output_flit.destination_endpoint;
            assign o_out_context_id[p*CX+:CX] = output_flit.context_id;
            assign o_out_message_type[p*MT+:MT] = output_flit.message_type;
            assign o_out_traffic_class[p*TC+:TC] = output_flit.traffic_class;
            assign o_out_packet_id[p*PI+:PI] = output_flit.packet_id;
            assign o_out_stream_last[p] = output_flit.stream_last;
            assign o_out_user_metadata[p*U+:U] = output_flit.user_metadata;
            assign o_out_error[p*ER+:ER] = output_flit.error;
            assign o_out_epoch[p*E+:E] = output_flit.epoch;
            assign o_out_parity[p] = ENABLE_LINK_PARITY == 1 && o_out_valid[p] ?
                ^ visible[FW-1:1] : 1'b0;
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t ps;
            /* verilator lint_on UNUSEDSIGNAL */
            assign ps = port_state[p];
            assign o_link_epoch[p*E+:E] = ps.epoch;
            assign o_input_packet_locked[p] = ps.input_locked;
            assign o_output_packet_locked[p] = ps.output_locked;

            event_barrier_state #(
                .WIDTH($bits(port_state_t)),
                .PROTECTED(BUFFER_PROTECTION != 0),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_state (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(port_next[p] != port_state[p]),
                .i_data(port_next[p]),
                .o_data(port_state[p]),
                .o_corrupt(port_corrupt[p])
            );

            event_barrier_state #(
                .WIDTH(FW),
                .PROTECTED(BUFFER_PROTECTION != 0),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_snapshot (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(snapshot_enable[p]),
                .i_data(snapshot_next[p]),
                .o_data(snapshot[p]),
                .o_corrupt(snapshot_corrupt[p])
            );

            if (OUTPUT_PIPELINE == 1) begin : g_output_pipeline
                wire unused_occupancy;
                wire unused_occupied;
                wire [FW-1:0] unused_contents;

                event_barrier_queue #(
                    .WIDTH(FW),
                    .DEPTH(1),
                    .PROTECTED(BUFFER_PROTECTION != 0),
                    .ASYNC_RESET(ASYNC_RESET != 0)
                ) u_output (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_flush(state_clear),
                    .i_valid(pipe_push[p]),
                    .o_ready(unused_pipe_ready[p]),
                    .i_data(pipe_input[p]),
                    .o_valid(pipe_valid[p]),
                    .i_ready(pipe_pop[p]),
                    .o_data(pipe_data[p]),
                    .o_occupancy(unused_occupancy),
                    .o_corrupt(pipe_corrupt[p]),
                    .o_occupied(unused_occupied),
                    .o_contents(unused_contents)
                );
            end else begin : g_no_output_pipeline
                assign pipe_valid[p] = 1'b0;
                assign unused_pipe_ready[p] = 1'b1;
                assign pipe_data[p] = '0;
                assign pipe_corrupt[p] = 1'b0;
            end
        end

        for (genvar k = 0; k < COUNT; k++) begin : g_input_vc
            wire [OCC-1:0] occupancy;

            noc_router_buffer #(
                .WIDTH(FW),
                .DEPTH(DEPTH),
                .PROTECTION(BUFFER_PROTECTION),
                .ASYNC_RESET(ASYNC_RESET != 0),
                .OWNERSHIP_MASK(OWN_MASK)
            ) u_buffer (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_flush(state_clear),
                .i_valid(queue_push[k]),
                .o_ready(queue_ready[k]),
                .i_data(queue_input[k]),
                .o_valid(queue_valid[k]),
                .i_ready(queue_pop[k]),
                .o_data(queue_head[k]),
                .o_occupancy(occupancy),
                .o_corrected(queue_corrected[k]),
                .o_uncorrectable(queue_bad[k]),
                .o_ownership_error(queue_ownership_bad[k])
            );

            assign o_input_vc_occupancy[k*OCC+:OCC] = occupancy;

            event_barrier_state #(
                .WIDTH($bits(ingress_t)),
                .PROTECTED(BUFFER_PROTECTION != 0),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_frame (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(frame_next[k] != frame[k]),
                .i_data(frame_next[k]),
                .o_data(frame[k]),
                .o_corrupt(frame_corrupt[k])
            );

            event_barrier_state #(
                .WIDTH(1),
                .PROTECTED(BUFFER_PROTECTION != 0),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_discard (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(discard_next[k] != discarding[k]),
                .i_data(discard_next[k]),
                .o_data(discarding[k]),
                .o_corrupt(discard_corrupt[k])
            );

            if (FLOW_CONTROL == 32'(FLOW_CREDIT)) begin : g_credit
                wire unused_overflow;
                wire unused_underflow;
                wire unused_terminal;
                wire [CW-1:0] next_credit = credit_return[k] ? credits[k] + 1'b1 :
                    credits[k] - 1'b1;

                counter #(
                    .WIDTH(CW),
                    .RESET_VALUE(CW'(CREDITS)),
                    .ASYNC_RESET(ASYNC_RESET != 0)
                ) u_credit (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_enable(1'b0),
                    .i_clear(state_clear),
                    .i_load(credit_return[k] ^ credit_launch[k]),
                    .i_direction(1'b0),
                    .i_load_value(next_credit),
                    .o_count(credits[k]),
                    .o_overflow(unused_overflow),
                    .o_underflow(unused_underflow),
                    .o_terminal(unused_terminal)
                );
            end else begin : g_no_credit
                assign credits[k] = '0;
            end

            assign o_output_credit_count[k*CW+:CW] = credits[k];
        end

        event_barrier_state #(
            .WIDTH(10),
            .PROTECTED(BUFFER_PROTECTION != 0),
            .ASYNC_RESET(ASYNC_RESET != 0)
        ) u_configuration (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(configure && configuration_legal),
            .i_data({i_config_fault_port_mask, i_config_port_enable}),
            .o_data({installed_fault, installed_enable}),
            .o_corrupt(configuration_corrupt)
        );

        event_barrier_state #(
            .WIDTH($bits(error_state_t)),
            .PROTECTED(BUFFER_PROTECTION != 0),
            .ASYNC_RESET(ASYNC_RESET != 0)
        ) u_errors (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(error_next != errors),
            .i_data(error_next),
            .o_data(errors),
            .o_corrupt(errors_corrupt)
        );

        for (genvar p = 0; p < 5; p++) begin : g_arbitration
            wire unused_contended;
            wire unused_pending;
            wire unused_locked;
            wire unused_lock;
            wire unused_accepted;
            wire [VW-1:0] unused_owner;
            wire [V-1:0] unused_onehot;

            round_robin_arbiter #(
                .NUM_REQUESTERS(V),
                .HAS_LOCK(0),
                .HOLD_PENDING(0),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_input (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_request(input_requests[p]),
                .i_eligible({V{1'b1}}),
                .i_lock({V{1'b0}}),
                .i_accept(input_accept[p]),
                .i_flush(state_clear),
                .o_grant_valid(input_grant_valid[p]),
                .o_grant_onehot(unused_onehot),
                .o_grant_index(input_grant[p]),
                .o_grant_lock(unused_lock),
                .o_grant_accepted(unused_accepted),
                .o_contended(unused_contended),
                .o_pending(unused_pending),
                .o_locked(unused_locked),
                .o_lock_owner(unused_owner),
                .o_protocol_error(arbiter_error[p])
            );

            for (genvar service = 0; service < 2; service++) begin : g_output
                localparam int ERROR_INDEX = 5 + 2 * p + service;
                wire [4:0] requests = service == 0 ? normal_requests[p] : high_requests[p];
                wire accept = service == 0 ? normal_accept[p] : high_accept[p];
                wire unused_c;
                wire unused_p;
                wire unused_l;
                wire unused_gl;
                wire unused_ga;
                wire [2:0] unused_o;
                wire [4:0] unused_oh;
                wire winner_valid;
                wire [2:0] winner;

                round_robin_arbiter #(
                    .NUM_REQUESTERS(5),
                    .HAS_LOCK(0),
                    .HOLD_PENDING(0),
                    .ASYNC_RESET(ASYNC_RESET)
                ) u_output (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_request(requests),
                    .i_eligible(5'b11111),
                    .i_lock(5'b00000),
                    .i_accept(accept),
                    .i_flush(state_clear),
                    .o_grant_valid(winner_valid),
                    .o_grant_onehot(unused_oh),
                    .o_grant_index(winner),
                    .o_grant_lock(unused_gl),
                    .o_grant_accepted(unused_ga),
                    .o_contended(unused_c),
                    .o_pending(unused_p),
                    .o_locked(unused_l),
                    .o_lock_owner(unused_o),
                    .o_protocol_error(arbiter_error[ERROR_INDEX])
                );

                if (service == 0) begin : g_normal
                    assign normal_valid[p] = winner_valid;
                    assign normal_grant[p] = winner;
                end else begin : g_high
                    assign high_valid[p] = winner_valid;
                    assign high_grant[p] = winner;
                end
            end
        end

        // No traffic-dependent state makes idle high. Configuration and error
        // clear use structural idleness; their own request does not deadlock ready.
        always_comb begin : idle_state
            /* verilator lint_off UNUSEDSIGNAL */
            ingress_t fs;
            port_state_t ps;
            /* verilator lint_on UNUSEDSIGNAL */
            idle = !(|queue_valid) && !(|pipe_valid) && !(|discarding);

            for (int k = 0; k < COUNT; k++) begin
                fs = frame[k];

                if (fs.open) idle = 1'b0;
            end

            for (int p = 0; p < 5; p++) begin
                ps = port_state[p];

                if (ps.input_locked || ps.output_locked || ps.pending) idle = 1'b0;
            end
        end
        always_comb begin : observe_state
            /* verilator lint_off UNUSEDSIGNAL */
            ingress_t fs;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t ps;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t other;
            /* verilator lint_on UNUSEDSIGNAL */
            configuration_legal = ( ^ {i_config_port_enable,
                i_config_fault_port_mask} !== 1'bx) && i_config_port_enable[0] &&
                !i_config_fault_port_mask[0];
            live_fatal = configuration_corrupt || errors_corrupt || (|port_corrupt) ||
                (|frame_corrupt) || (|discard_corrupt) || (|queue_ownership_bad) ||
                (|pipe_corrupt) || (|snapshot_corrupt) || (|arbiter_error);
            parity_error = '0;

            for (int k = 0; k < COUNT; k++) begin
                fs = frame[k];

                if (( ^ frame[k] === 1'bx) ||
                    (queue_valid[k] && ( ^ queue_head[k] === 1'bx))) live_fatal = 1'b1;

                if (FLOW_CONTROL == 32'(FLOW_CREDIT) && credit_out_of_range({1'b0, credits[k]}))
                    live_fatal = 1'b1;
            end

            for (int p = 0; p < 5; p++) begin
                ps = port_state[p];

                if (!cardinal_legal(p) && i_config_port_enable[p] &&
                    !i_config_fault_port_mask[p]) configuration_legal = 1'b0;

                if ((ps.input_locked && (32'(ps.input_vc) >= V || 32'(ps.route) >= 5)) ||
                    (ps.output_locked && (32'(ps.owner) >= 5 || 32'(ps.output_vc) >= V)) ||
                    (ps.pending && (32'(ps.pending_owner) >= 5 || 32'(ps.pending_vc) >= V)))
                    live_fatal = 1'b1;

                for (int q = 0; q < 5; q++) begin
                    other = port_state[q];

                    if (ps.output_locked && other.input_locked && 32'(ps.owner) == q &&
                        (32'(other.route) != p || ps.output_vc != other.input_vc))
                        live_fatal = 1'b1;

                    if (p != q && ps.output_locked && other.output_locked &&
                        ps.owner == other.owner) live_fatal = 1'b1;
                end

                if (ENABLE_LINK_PARITY == 1 && (i_rstb === 1'b1) &&
                    (i_flush === 1'b0) && !configure && usable[p] &&
                    (i_in_valid[p] === 1'b1) &&
                    ( ^ {incoming[p][FW-1:1], i_in_parity[p]} !== 1'b0)) begin
                    parity_error[p] = 1'b1;
                    live_fatal = 1'b1;
                end
            end
        end

        always_comb begin
            running = (i_rstb === 1'b1) && (i_flush === 1'b0) &&
                (i_drain === 1'b0 || i_drain === 1'b1) &&
                (i_config_valid === 1'b0 || i_config_valid === 1'b1) && !configure &&
                (i_error_clear === 1'b0 || i_error_clear === 1'b1) &&
                !error_value.fatal && !live_fatal;
        end

        // Eligibility depends on buffered heads and registered ownership, never
        // on an upstream valid or downstream ready spanning another router.
        always_comb begin : vc_requests
            /* verilator lint_off UNUSEDSIGNAL */
            flit_t f;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t ps;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t os;
            /* verilator lint_on UNUSEDSIGNAL */
            int destination;

            f = '0;
            ps = '0;
            os = '0;
            destination = 0;

            for (int p = 0; p < 5; p++) input_requests[p] = '0;

            for (int p = 0; p < 5; p++) begin
                ps = port_state[p];

                if (running && !ps.input_locked) begin
                    for (int v = 0; v < V; v++) begin
                        f = queue_head[p*V+v];
                        destination = route(f.destination_node);

                        if (queue_valid[p*V+v]) begin
                            if (discarding[p*V+v] || f.discard || !f.head || destination >= 5)
                                input_requests[p][v] = 1'b1;
                            else begin
                                os = port_state[destination];

                                if (!usable[destination] || !cardinal_legal(destination) ||
                                    (!os.output_locked && (FLOW_CONTROL != 32'(FLOW_CREDIT) ||
                                    PACKET_CREDIT_RESERVATION == 0 ||
                                    32'(credits[destination*V+v]) >= PACKET_CREDIT_RESERVATION)))
                                    input_requests[p][v] = 1'b1;
                            end
                        end
                    end
                end

                for (int o = 0; o < 5; o++) begin
                    os = port_state[o];

                    if (running && os.pending && 32'(os.pending_owner) == p) begin
                        input_requests[p] = '0;
                        input_requests[p][os.pending_vc] = queue_valid[p*V+int'(os.pending_vc)];
                    end
                end
            end
        end

        always_comb begin : choose_input
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t ps;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t os;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            flit_t f;
            /* verilator lint_on UNUSEDSIGNAL */
            int v;
            int destination;
            bit forced;
            f = '0;
            destination = 0;
            input_candidate_valid = '0;
            input_candidate_drop = '0;
            input_high = '0;

            for (int p = 0; p < 5; p++) begin
                ps = port_state[p];
                v = int'(input_grant[p]);
                forced = ps.input_locked;

                if (ps.input_locked) v = int'(ps.input_vc);

                for (int o = 0; o < 5; o++) begin
                    os = port_state[o];

                    if (os.pending && 32'(os.pending_owner) == p) begin
                        v = int'(os.pending_vc);
                        forced = 1'b1;
                    end
                end

                input_candidate_vc[p] = VW'(v);
                input_route[p] = '0;
                input_flit[p] = '0;

                if (running && v < V && (forced || input_grant_valid[p]) &&
                    queue_valid[p*V+v]) begin
                    f = queue_head[p*V+v];

                    if (queue_bad[p*V+v]) f.error = '1;

                    destination = ps.input_locked ? int'(ps.route) : route(f.destination_node);
                    input_candidate_valid[p] = 1'b1;
                    input_flit[p] = f;
                    input_route[p] = 3'(destination);
                    input_candidate_drop[p] = !ps.input_locked &&
                        (discarding[p*V+v] || f.discard || !f.head || destination >= 5);

                    if (!ps.input_locked && destination < 5 && !usable[destination])
                        input_candidate_drop[p] = 1'b1;

                    if (class_legal(f.traffic_class) && ENABLE_QOS == 1)
                        input_high[p] = TRAFFIC_CLASS_TO_SERVICE[f.traffic_class];
                end
            end
        end

        always_comb begin : output_requests
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t os;
            /* verilator lint_on UNUSEDSIGNAL */

            for (int o = 0; o < 5; o++) begin
                os = port_state[o];
                normal_requests[o] = '0;
                high_requests[o] = '0;
                normal_waiting[o] = 1'b0;

                for (int p = 0; p < 5; p++) begin
                    if (input_candidate_valid[p] && !input_candidate_drop[p] &&
                        !input_high[p] && 32'(input_route[p]) == o)
                        normal_waiting[o] = 1'b1;
                end

                if (os.pending) begin
                    if (os.pending_high) high_requests[o][os.pending_owner] = 1'b1;
                    else normal_requests[o][os.pending_owner] = 1'b1;
                end else if (!os.output_locked) begin
                    for (int p = 0; p < 5; p++) begin
                        if (input_candidate_valid[p] && !input_candidate_drop[p] &&
                            32'(input_route[p]) == o) begin

                            if (input_high[p]) high_requests[o][p] = 1'b1;
                            else normal_requests[o][p] = 1'b1;
                        end
                    end
                end
            end
        end

        always_comb begin : choose_output
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t os;
            /* verilator lint_on UNUSEDSIGNAL */
            int p;
            selected_valid = '0;
            selected_high = '0;

            for (int o = 0; o < 5; o++) begin
                os = port_state[o];
                p = 0;
                selected_vc[o] = '0;
                selected_flit[o] = '0;

                if (os.output_locked) begin
                    p = int'(os.owner);
                    selected_vc[o] = os.output_vc;
                end else if (os.pending) begin
                    p = int'(os.pending_owner);
                    selected_vc[o] = os.pending_vc;
                    selected_high[o] = os.pending_high;
                end else begin
                    if (high_valid[o] && (!normal_valid[o] ||
                        32'(os.high_budget) < SERVICE_LIMIT)) begin
                        p = int'(high_grant[o]);
                        selected_high[o] = 1'b1;
                    end else p = int'(normal_grant[o]);

                    if (p < 5) selected_vc[o] = input_candidate_vc[p];
                end

                selected_owner[o] = 3'(p);

                if (running && p < 5 && input_candidate_valid[p] &&
                    !input_candidate_drop[p] && 32'(input_route[p]) == o &&
                    (os.output_locked || os.pending || normal_valid[o] || high_valid[o])) begin
                    selected_valid[o] = 1'b1;
                    selected_flit[o] = os.pending ? snapshot[o] : input_flit[p];
                end
            end
        end

        always_comb begin : switch_and_links
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t os;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            flit_t f;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            flit_t stored;
            /* verilator lint_on UNUSEDSIGNAL */
            int v;
            queue_pop = '0;
            pipe_push = '0;
            pipe_pop = '0;
            switch_fire = '0;
            link_transfer = '0;
            o_out_valid = '0;
            output_stall = '0;
            credit_starved = '0;
            head_event = '0;
            tail_event = '0;
            input_accept = '0;
            normal_accept = '0;
            high_accept = '0;
            credit_launch = '0;

            for (int o = 0; o < 5; o++) begin
                os = port_state[o];
                f = OUTPUT_PIPELINE == 1 ? pipe_data[o] : selected_flit[o];
                stored = pipe_data[o];
                pipe_input[o] = selected_flit[o];
                outgoing[o] = '0;
                v = int'(f.vc);

                if (running && usable[o] && v < V) begin
                    if ((OUTPUT_PIPELINE == 1 ? pipe_valid[o] : selected_valid[o]) &&
                        (FLOW_CONTROL == 32'(FLOW_VALID_READY) || credits[o*V+v] != 0)) begin
                        o_out_valid[o] = 1'b1;
                        f.epoch = os.epoch;
                        outgoing[o] = f;
                        link_transfer[o] = FLOW_CONTROL == 32'(FLOW_CREDIT) ||
                            (i_out_ready[o] === 1'b1);
                    end

                    if (OUTPUT_PIPELINE == 1) begin
                        pipe_pop[o] = link_transfer[o];
                        pipe_push[o] = selected_valid[o] && (!pipe_valid[o] || pipe_pop[o]) &&
                            !(pipe_valid[o] && stored.tail);
                        switch_fire[o] = pipe_push[o];
                    end else switch_fire[o] = link_transfer[o];

                    if (FLOW_CONTROL == 32'(FLOW_CREDIT) &&
                        (OUTPUT_PIPELINE == 1 ? pipe_valid[o] : selected_valid[o]) &&
                        credits[o*V+v] == 0) credit_starved[o] = 1'b1;

                    output_stall[o] = (OUTPUT_PIPELINE == 1 ? pipe_valid[o] : selected_valid[o]) &&
                        !link_transfer[o];

                    if (link_transfer[o]) begin
                        if (FLOW_CONTROL == 32'(FLOW_CREDIT)) credit_launch[o*V+v] = 1'b1;
                        if (f.tail) tail_event[o] = 1'b1;
                    end

                    if (switch_fire[o]) begin
                        queue_pop[int'(selected_owner[o])*V+int'(selected_vc[o])] = 1'b1;

                        if (!os.output_locked) begin
                            head_event[o] = 1'b1;
                            input_accept[selected_owner[o]] = 1'b1;

                            if (!os.pending) begin
                                if (selected_high[o]) high_accept[o] = 1'b1;
                                else normal_accept[o] = 1'b1;
                            end else begin
                                // The candidate remains in its service arbiter's request set
                                // while pending; acceptance is qualified below in the adapter.
                                if (selected_high[o]) high_accept[o] = 1'b1;
                                else normal_accept[o] = 1'b1;
                            end
                        end
                    end
                end
            end

            for (int p = 0; p < 5; p++) begin
                if (running && input_candidate_valid[p] && input_candidate_drop[p]) begin
                    queue_pop[p*V+int'(input_candidate_vc[p])] = 1'b1;
                    input_accept[p] = 1'b1;
                end
            end
        end

        always_comb begin : ingress_and_discard
            /* verilator lint_off UNUSEDSIGNAL */
            flit_t f;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            ingress_t fs;
            /* verilator lint_on UNUSEDSIGNAL */
            int v;
            /* verilator lint_off UNUSEDSIGNAL */
            int k;
            /* verilator lint_on UNUSEDSIGNAL */
            bit known_flit;
            bit bad_start;
            bit violation;
            bit accepted;
            fs = '0;
            k = 0;
            bad_start = 1'b0;
            violation = 1'b0;
            o_in_ready = '0;
            accepted_input = '0;
            sink_input = '0;
            input_stall = '0;
            protocol_error = '0;
            route_error = '0;
            buffer_corrected = '0;
            buffer_bad = '0;
            input_credit = '0;
            input_credit_vc = '0;
            input_credit_epoch = '0;
            queue_push = '0;
            discard_next = discarding;

            for (int index = 0; index < COUNT; index++) begin
                queue_input[index] = '0;
                frame_next[index] = frame[index];
            end

            for (int p = 0; p < 5; p++) begin
                f = incoming[p];
                v = int'(f.vc);
                known_flit = ( ^ incoming[p] !== 1'bx);
                accepted = 1'b0;

                if (running && usable[p] && (i_in_valid[p] === 1'b1)) begin
                    if (known_flit && (v >= V || f.epoch != o_link_epoch[p*E+:E])) begin
                        accepted = 1'b1;
                        sink_input[p] = 1'b1;
                    end else if (known_flit && v < V) begin
                        fs = frame[p*V+v];

                        if (i_drain === 1'b0 || fs.open) begin
                            if (FLOW_CONTROL == 32'(FLOW_VALID_READY)) begin
                                o_in_ready[p] = queue_ready[p*V+v];
                                accepted = queue_ready[p*V+v];
                            end else accepted = queue_ready[p*V+v];

                            if (accepted) begin
                                k = p * V + v;
                                bad_start = !fs.open && (!f.head || f.fragment_index != 0 ||
                                    f.source_node >= N'(NODE_COUNT) ||
                                    !class_legal(f.traffic_class));

                                if (class_legal(f.traffic_class) &&
                                    TRAFFIC_CLASS_TO_VC[int'(f.traffic_class)*VW+:VW] != f.vc)
                                    bad_start = !fs.open;

                                violation = bad_start || (fs.open && (f.head ||
                                    {1'b0, f.fragment_index} != fs.next_fragment ||
                                    ((incoming[p] ^ fs.invariant) & INV_MASK) != 0));

                                if (!class_legal(f.traffic_class)) violation = 1'b1;
                                else if (TRAFFIC_CLASS_TO_VC[int'(f.traffic_class)*VW+:VW] != f.vc)
                                    violation = 1'b1;

                                if (!fs.open) begin
                                    fs.quarantine = bad_start;
                                    fs.invariant = incoming[p] & INV_MASK;
                                    fs.bad = violation;
                                end else fs.bad = fs.bad || violation;

                                f.discard = fs.quarantine;

                                if (fs.bad) f.error = '1;

                                if (violation || f.error != 0) protocol_error[p] = 1'b1;

                                fs.next_fragment = {1'b0, f.fragment_index} + 1'b1;
                                fs.open = !f.tail;

                                if (f.tail) begin
                                    fs.quarantine = 1'b0;
                                    fs.bad = 1'b0;
                                end

                                frame_next[k] = fs;
                                queue_push[k] = 1'b1;
                                queue_input[k] = f;
                            end
                        end
                    end

                    if (sink_input[p] && FLOW_CONTROL == 32'(FLOW_VALID_READY))
                        o_in_ready[p] = 1'b1;

                    accepted_input[p] = accepted;
                    input_stall[p] = !accepted;
                end

                for (int vc = 0; vc < V; vc++) begin
                    k = p * V + vc;

                    if (queue_valid[k] && queue_ownership_bad[k] && !error_value.fatal)
                        buffer_bad[p] = 1'b1;

                    if (queue_pop[k]) begin
                        f = queue_head[k];

                        if (input_candidate_drop[p]) begin
                            if (!discarding[k]) route_error[p] = 1'b1;
                            discard_next[k] = !f.tail;
                        end

                        buffer_corrected[p] = queue_corrected[k];
                        buffer_bad[p] = queue_bad[k];

                        if (FLOW_CONTROL == 32'(FLOW_CREDIT)) begin
                            input_credit[p] = 1'b1;
                            input_credit_vc[p*VW+:VW] = VW'(vc);
                            input_credit_epoch[p*E+:E] = o_link_epoch[p*E+:E];
                        end
                    end
                end
            end

            if (flush) begin
                queue_push = '0;
                accepted_input = '0;
                discard_next = '0;

                for (int index = 0; index < COUNT; index++) frame_next[index] = '0;
            end
        end

        always_comb begin : update_ports
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t prior;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t ps;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            port_state_t owner;
            /* verilator lint_on UNUSEDSIGNAL */
            /* verilator lint_off UNUSEDSIGNAL */
            flit_t f;
            /* verilator lint_on UNUSEDSIGNAL */
            int p;

            p = 0;
            owner = '0;

            for (int o = 0; o < 5; o++) begin
                port_next[o] = port_state[o];
                snapshot_next[o] = snapshot[o];
            end

            snapshot_enable = '0;

            // Output retirement releases the input resource even if its tail
            // had already popped into the optional holding stage.
            for (int o = 0; o < 5; o++) begin
                ps = port_next[o];
                f = outgoing[o];

                if (link_transfer[o] && f.tail && ps.output_locked) begin
                    p = int'(ps.owner);
                    owner = port_next[p];
                    owner.input_locked = 1'b0;
                    port_next[p] = owner;
                    ps = port_next[o];
                    ps.output_locked = 1'b0;
                    ps.pending = 1'b0;
                    port_next[o] = ps;
                end
            end

            for (int o = 0; o < 5; o++) begin
                ps = port_next[o];
                prior = port_state[o];

                if (selected_valid[o] && !switch_fire[o] &&
                    !prior.output_locked && !ps.pending) begin
                    ps.pending = 1'b1;
                    ps.pending_owner = selected_owner[o];
                    ps.pending_vc = selected_vc[o];
                    ps.pending_high = selected_high[o];
                    snapshot_enable[o] = 1'b1;
                    snapshot_next[o] = selected_flit[o];
                end

                if (switch_fire[o]) begin
                    f = selected_flit[o];
                    ps.pending = 1'b0;

                    if (!prior.output_locked) begin
                        if (ENABLE_QOS == 1 && selected_high[o] && normal_waiting[o]) begin
                            if (32'(ps.high_budget) < SERVICE_LIMIT)
                                ps.high_budget = ps.high_budget + 1'b1;
                        end else ps.high_budget = '0;
                    end

                    if (OUTPUT_PIPELINE == 1 || !f.tail) begin
                        ps.output_locked = 1'b1;
                        ps.owner = selected_owner[o];
                        ps.output_vc = selected_vc[o];
                        p = int'(selected_owner[o]);
                        owner = port_next[p];
                        owner.input_locked = 1'b1;
                        owner.input_vc = selected_vc[o];
                        owner.route = 3'(o);
                        port_next[p] = owner;

                        // Preserve simultaneous changes when local input and
                        // local output share the same physical-port record.
                        if (p == o) begin
                            ps.input_locked = 1'b1;
                            ps.input_vc = selected_vc[o];
                            ps.route = 3'(o);
                        end
                    end
                end

                port_next[o] = ps;
            end

            if (flush) begin
                snapshot_enable = '0;

                for (int o = 0; o < 5; o++) begin
                    ps = port_state[o];
                    owner = '0;
                    owner.epoch = ps.epoch + 1'b1;
                    port_next[o] = owner;
                end
            end
        end

        always_comb begin : returned_credits
            int vc;
            credit_return = '0;

            for (int p = 0; p < 5; p++) begin
                vc = int'(i_out_credit_vc[p*VW+:VW]);

                if (running && FLOW_CONTROL == 32'(FLOW_CREDIT) && usable[p] &&
                    (i_out_credit_valid[p] === 1'b1) &&
                    ( ^ {i_out_credit_vc[p*VW+:VW], i_out_credit_epoch[p*E+:E]} !== 1'bx) &&
                    vc < V && i_out_credit_epoch[p*E+:E] == o_link_epoch[p*E+:E] &&
                    (32'(credits[p*V+vc]) < CREDITS || credit_launch[p*V+vc]))
                    credit_return[p*V+vc] = 1'b1;
            end
        end

        always_comb begin : error_detection
            /* verilator lint_off UNUSEDSIGNAL */
            flit_t f;
            /* verilator lint_on UNUSEDSIGNAL */
            int vc;
            unknown_control = ( ^ {i_rstb, i_flush, i_drain, i_error_clear,
                i_config_valid, i_in_valid} === 1'bx);

            if (FLOW_CONTROL == 32'(FLOW_CREDIT))
                unknown_control = unknown_control || ( ^ i_out_credit_valid === 1'bx);
            else unknown_control = unknown_control || ( ^ i_out_ready === 1'bx);

            fault_event = live_fatal;
            detected_error = live_fatal ? ROUTER_ERR_OWNERSHIP : ROUTER_ERR_NONE;

            if ((|queue_bad) && (|queue_ownership_bad))
                detected_error = BUFFER_PROTECTION == 32'(BUFFER_PROTECTION_PARITY) ?
                    ROUTER_ERR_PARITY : ROUTER_ERR_UNCORRECTABLE;
            if (|parity_error) detected_error = ROUTER_ERR_PARITY;

            for (int p = 0; p < 5; p++) begin
                f = incoming[p];
                vc = int'(f.vc);

                if ((i_in_valid[p] === 1'b1) && !usable[p]) begin
                    fault_event = 1'b1;

                    if (detected_error == ROUTER_ERR_NONE) detected_error = ROUTER_ERR_PORT;
                end

                if (running && usable[p] && (i_in_valid[p] === 1'b1)) begin
                    if ( ^ incoming[p] === 1'bx) unknown_control = 1'b1;
                    else if (vc >= V || sink_input[p]) begin
                        fault_event = 1'b1;

                        if (detected_error == ROUTER_ERR_NONE)
                            detected_error = vc >= V ? ROUTER_ERR_RANGE : ROUTER_ERR_EPOCH;
                    end else if (FLOW_CONTROL == 32'(FLOW_CREDIT) &&
                        !queue_ready[p*V+vc]) begin
                        fault_event = 1'b1;

                        if (detected_error == ROUTER_ERR_NONE) detected_error = ROUTER_ERR_OVERFLOW;
                    end
                end

                if (FLOW_CONTROL == 32'(FLOW_CREDIT) && running &&
                    (i_out_credit_valid[p] === 1'b1)) begin
                    vc = int'(i_out_credit_vc[p*VW+:VW]);

                    if ( ^ {i_out_credit_vc[p*VW+:VW], i_out_credit_epoch[p*E+:E]} === 1'bx)
                        unknown_control = 1'b1;
                    else if (!usable[p] || vc >= V || !credit_return[p*V+vc]) begin
                        fault_event = 1'b1;
                        if (detected_error == ROUTER_ERR_NONE) detected_error = ROUTER_ERR_CREDIT;
                    end
                end

                if (buffer_bad[p] || buffer_corrected[p] ||
                    route_error[p] || protocol_error[p]) begin
                    fault_event = 1'b1;

                    if (detected_error == ROUTER_ERR_NONE) begin
                        if (buffer_bad[p]) detected_error = ROUTER_ERR_UNCORRECTABLE;
                        else if (buffer_corrected[p]) detected_error = ROUTER_ERR_CORRECTED;
                        else if (route_error[p]) detected_error = ROUTER_ERR_RANGE;
                        else if (!class_legal(f.traffic_class))
                            detected_error = ROUTER_ERR_CLASS;
                        else if (TRAFFIC_CLASS_TO_VC[int'(f.traffic_class)*VW+:VW] != f.vc)
                            detected_error = ROUTER_ERR_CLASS;
                        else detected_error = ROUTER_ERR_PROTOCOL;
                    end
                end
            end

            if (configure && !configuration_legal) begin
                fault_event = 1'b1;

                if (detected_error == ROUTER_ERR_NONE) detected_error = ROUTER_ERR_CONFIG;
            end

            if (unknown_control) begin
                fault_event = 1'b1;

                if (detected_error == ROUTER_ERR_NONE) detected_error = ROUTER_ERR_UNKNOWN;
            end
        end

        always_comb begin : update_errors
            error_state_t next_error;
            next_error = error_value;

            if (flush || (idle && i_error_clear === 1'b1 && i_flush === 1'b0)) begin
                if (!next_error.fatal) next_error = '0;
            end

            if ((i_rstb === 1'b1) && !flush && fault_event) begin
                if (!next_error.error) next_error.code = detected_error;

                next_error.error = 1'b1;

                if (live_fatal || detected_error == ROUTER_ERR_OVERFLOW)
                    next_error.fatal = 1'b1;
            end

            error_next = next_error;
        end

        always_comb begin : starvation_events
            vc_starved = '0;

            for (int p = 0; p < 5; p++) begin
                if (running && (|input_requests[p]) && !input_accept[p] &&
                    !queue_pop[p*V+int'(input_candidate_vc[p])]) vc_starved[p] = 1'b1;
            end
        end

        wire [5*(8+VW+E)-1:0] pulse_next = {
            accepted_input, link_transfer, head_event, tail_event, input_stall,
            output_stall, vc_starved, credit_starved, input_credit_vc, input_credit_epoch
        };
        wire [5*(8+VW+E)-1:0] pulse_state;
        wire [4:0] credit_state;
        wire [24:0] diagnostic_state;
        wire accepted_configuration;
        wire rejected_configuration;
        wire flushed_state;

        dff #(.WIDTH(5 * (8 + VW + E)), .ASYNC_RESET(ASYNC_RESET != 0)) u_events (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(1'b1),
            .i_d(flush ? '0 : pulse_next),
            .o_q(pulse_state)
        );

        assign {o_event_input_accept, o_event_output_transfer, o_event_packet_head,
            o_event_packet_tail, o_event_input_stall, o_event_output_stall,
            o_event_vc_starved, o_event_credit_starved, o_in_credit_vc,
            o_in_credit_epoch} = (i_rstb === 1'b1) ? pulse_state : '0;

        dff #(.WIDTH(5), .ASYNC_RESET(ASYNC_RESET != 0)) u_credit_events (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(1'b1),
            .i_d(flush ? 5'b00000 : input_credit),
            .o_q(credit_state)
        );

        assign o_in_credit_valid = (i_rstb === 1'b1) ? credit_state : '0;

        dff #(.WIDTH(25), .ASYNC_RESET(ASYNC_RESET != 0)) u_diagnostics (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(1'b1),
            .i_d(flush ? 25'b0 : {route_error, protocol_error, parity_error,
                buffer_corrected, buffer_bad}),
            .o_q(diagnostic_state)
        );

        assign {o_event_route_error, o_event_protocol_error, o_event_parity_error,
            o_event_buffer_corrected, o_event_buffer_uncorrectable} =
            (i_rstb === 1'b1) ? diagnostic_state : '0;

        dff #(.WIDTH(3), .ASYNC_RESET(ASYNC_RESET != 0)) u_control_events (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(1'b1),
            .i_d({configure && configuration_legal, configure && !configuration_legal,
                flush && !idle}),
            .o_q({accepted_configuration, rejected_configuration, flushed_state})
        );

        assign o_config_accepted = accepted_configuration;
        assign o_config_rejected = rejected_configuration;
        assign o_flushed = flushed_state;
`ifdef MOSAIC_NOC_ROUTER_ASSERTIONS
        wire [5*FW-1:0] checked_output;
        wire [14:0] checked_owner;
        wire [5*VW-1:0] checked_vc;
        for (genvar p = 0; p < 5; p++) begin : g_checked_link
            assign checked_output[p*FW+:FW] = {
                o_out_data[p*D+:D],
                o_out_keep[p*K+:K],
                o_out_head[p],
                o_out_tail[p],
                o_out_fragment_index[p*F+:F],
                o_out_vc[p*VW+:VW],
                o_out_source_node[p*N+:N],
                o_out_source_endpoint[p*EP+:EP],
                o_out_destination_node[p*N+:N],
                o_out_destination_endpoint[p*EP+:EP],
                o_out_context_id[p*CX+:CX],
                o_out_message_type[p*MT+:MT],
                o_out_traffic_class[p*TC+:TC],
                o_out_packet_id[p*PI+:PI],
                o_out_stream_last[p],
                o_out_user_metadata[p*U+:U],
                o_out_error[p*ER+:ER],
                o_out_epoch[p*E+:E],
                1'b0
            };
            assign checked_owner[p*3+:3] = selected_owner[p];
            assign checked_vc[p*VW+:VW] = selected_vc[p];
        end
        noc_router_assertions #(.V(V), .DEPTH(DEPTH), .CREDITS(CREDITS),
            .FLOW(FLOW_CONTROL), .FW(FW), .E(E)) u_assertions (
            .i_integrity_bad(live_fatal), .i_fatal(o_fatal_error),
            .i_observed_output(checked_output), .i_pops(queue_pop), .i_switch(switch_fire),
            .i_owner(checked_owner), .i_selected_vc(checked_vc), .*
        );
`endif
    end
endmodule
