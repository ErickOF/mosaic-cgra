`timescale 1ns / 1ps

// Verification fixture: actual router instances, direct credit links and one
// released skid buffer per valid-ready link. Flush discards bridge state through
// its synchronous ready path, without deriving a reset from flush.
module noc_router_mesh_tb #(
    parameter MESH_X = 2,
    parameter MESH_Y = 2,
    parameter NUM_VCS = 2,
    parameter FLOW_CONTROL = 1,
    parameter ROUTING_ALGORITHM = 0,
    parameter ASYNC_RESET = 0,
    localparam int NN = MESH_X * MESH_Y,
    localparam int VW = NUM_VCS > 1 ? $clog2(NUM_VCS) : 1,
    localparam int LW = 113 + VW
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_drain,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_config_valid,
    input logic [5*NN-1:0] i_config_port_enable,
    input logic [5*NN-1:0] i_config_fault_port_mask,
    output wire o_config_ready,
    output wire o_config_accepted,
    output wire o_config_rejected,
    input logic [NN-1:0] i_in_valid,
    output wire [NN-1:0] o_in_ready,
    input logic [NN*32-1:0] i_in_data,
    input logic [NN*4-1:0] i_in_keep,
    input logic [NN*1-1:0] i_in_head,
    input logic [NN*1-1:0] i_in_tail,
    input logic [NN*4-1:0] i_in_fragment_index,
    input logic [NN*VW-1:0] i_in_vc,
    input logic [NN*8-1:0] i_in_source_node,
    input logic [NN*4-1:0] i_in_source_endpoint,
    input logic [NN*8-1:0] i_in_destination_node,
    input logic [NN*4-1:0] i_in_destination_endpoint,
    input logic [NN*8-1:0] i_in_context_id,
    input logic [NN*4-1:0] i_in_message_type,
    input logic [NN*3-1:0] i_in_traffic_class,
    input logic [NN*8-1:0] i_in_packet_id,
    input logic [NN*1-1:0] i_in_stream_last,
    input logic [NN*16-1:0] i_in_user_metadata,
    input logic [NN*4-1:0] i_in_error,
    input logic [NN*2-1:0] i_in_epoch,
    input logic [NN-1:0] i_in_parity,
    output wire [NN-1:0] o_out_valid,
    input logic [NN-1:0] i_out_ready,
    output wire [NN*32-1:0] o_out_data,
    output wire [NN*4-1:0] o_out_keep,
    output wire [NN*1-1:0] o_out_head,
    output wire [NN*1-1:0] o_out_tail,
    output wire [NN*4-1:0] o_out_fragment_index,
    output wire [NN*VW-1:0] o_out_vc,
    output wire [NN*8-1:0] o_out_source_node,
    output wire [NN*4-1:0] o_out_source_endpoint,
    output wire [NN*8-1:0] o_out_destination_node,
    output wire [NN*4-1:0] o_out_destination_endpoint,
    output wire [NN*8-1:0] o_out_context_id,
    output wire [NN*4-1:0] o_out_message_type,
    output wire [NN*3-1:0] o_out_traffic_class,
    output wire [NN*8-1:0] o_out_packet_id,
    output wire [NN*1-1:0] o_out_stream_last,
    output wire [NN*16-1:0] o_out_user_metadata,
    output wire [NN*4-1:0] o_out_error,
    output wire [NN*2-1:0] o_out_epoch,
    output wire [NN-1:0] o_out_parity,
    input logic [NN-1:0] i_out_credit_valid,
    input logic [NN*VW-1:0] i_out_credit_vc,
    input logic [NN*2-1:0] i_out_credit_epoch,
    output wire [NN-1:0] o_in_credit_valid,
    output wire [NN*VW-1:0] o_in_credit_vc,
    output wire [NN*2-1:0] o_in_credit_epoch,
    output wire [NN*5-1:0] o_active_port_enable,
    output wire [NN*5-1:0] o_active_fault_port_mask,
    output wire [NN*5*2-1:0] o_link_epoch,
    output wire [NN*5*NUM_VCS*2-1:0] o_input_vc_occupancy,
    output wire [NN*5*NUM_VCS*2-1:0] o_output_credit_count,
    output wire [NN*5-1:0] o_input_packet_locked,
    output wire [NN*5-1:0] o_output_packet_locked,
    output wire o_idle,
    output wire o_quiescent,
    output wire o_drain_done,
    output wire o_flushed,
    output wire o_error,
    output logic [4:0] o_error_code,
    output wire o_fatal_error,
    output wire [NN-1:0] o_event_input_accept,
    output wire [NN-1:0] o_event_output_transfer,
    output wire [NN-1:0] o_event_packet_head,
    output wire [NN-1:0] o_event_packet_tail,
    output wire [NN-1:0] o_event_input_stall,
    output wire [NN-1:0] o_event_output_stall,
    output wire [NN-1:0] o_event_vc_starved,
    output wire [NN-1:0] o_event_credit_starved,
    output wire [NN-1:0] o_event_route_error,
    output wire [NN-1:0] o_event_protocol_error,
    output wire [NN-1:0] o_event_parity_error,
    output wire [NN-1:0] o_event_buffer_corrected,
    output wire [NN-1:0] o_event_buffer_uncorrectable
);
    wire [4:0] in_valid[NN];
    wire [4:0] in_ready[NN];
    wire [4:0] in_parity[NN];
    wire [4:0] out_valid[NN];
    wire [4:0] out_ready[NN];
    wire [4:0] out_parity[NN];
    wire [4:0] return_valid[NN];
    wire [5*VW-1:0] return_vc[NN];
    wire [9:0] return_epoch[NN];
    wire [4:0] credit_valid[NN];
    wire [5*VW-1:0] credit_vc[NN];
    wire [9:0] credit_epoch[NN];
    wire [NN-1:0] config_ready;
    wire [NN-1:0] config_accepted;
    wire [NN-1:0] config_rejected;
    wire [NN-1:0] idle;
    wire [NN-1:0] quiescent;
    wire [NN-1:0] drain_done;
    wire [NN-1:0] flushed;
    wire [NN-1:0] error_flag;
    wire [NN-1:0] fatal;
    wire [4:0] error_code[NN];
    wire [NN*5-1:0] bridge_valid;
    logic bridge_flushed;
    assign o_config_ready = &config_ready;
    assign o_config_accepted = &config_accepted;
    assign o_config_rejected = |config_rejected;
    assign o_idle = (&idle) && !(|bridge_valid);
    assign o_quiescent = (&quiescent) && !(|bridge_valid);
    assign o_drain_done = (&drain_done) && !(|bridge_valid);
    assign o_flushed = (|flushed) || bridge_flushed;
    assign o_error = |error_flag;
    assign o_fatal_error = |fatal;
    always_comb begin
        o_error_code = '0;
        for (int n = 0; n < NN; n ++ )
            if (o_error_code == 0) o_error_code = error_code[n];
    end
    always_ff @(posedge i_clk) begin
        if (!i_rstb) bridge_flushed <= 1'b0;
        else bridge_flushed <= i_flush && (|bridge_valid);
    end
    wire [5*32-1:0] in_data[NN];
    wire [5*32-1:0] out_data[NN];
    wire [5*4-1:0] in_keep[NN];
    wire [5*4-1:0] out_keep[NN];
    wire [5*1-1:0] in_head[NN];
    wire [5*1-1:0] out_head[NN];
    wire [5*1-1:0] in_tail[NN];
    wire [5*1-1:0] out_tail[NN];
    wire [5*4-1:0] in_fragment_index[NN];
    wire [5*4-1:0] out_fragment_index[NN];
    wire [5*VW-1:0] in_vc[NN];
    wire [5*VW-1:0] out_vc[NN];
    wire [5*8-1:0] in_source_node[NN];
    wire [5*8-1:0] out_source_node[NN];
    wire [5*4-1:0] in_source_endpoint[NN];
    wire [5*4-1:0] out_source_endpoint[NN];
    wire [5*8-1:0] in_destination_node[NN];
    wire [5*8-1:0] out_destination_node[NN];
    wire [5*4-1:0] in_destination_endpoint[NN];
    wire [5*4-1:0] out_destination_endpoint[NN];
    wire [5*8-1:0] in_context_id[NN];
    wire [5*8-1:0] out_context_id[NN];
    wire [5*4-1:0] in_message_type[NN];
    wire [5*4-1:0] out_message_type[NN];
    wire [5*3-1:0] in_traffic_class[NN];
    wire [5*3-1:0] out_traffic_class[NN];
    wire [5*8-1:0] in_packet_id[NN];
    wire [5*8-1:0] out_packet_id[NN];
    wire [5*1-1:0] in_stream_last[NN];
    wire [5*1-1:0] out_stream_last[NN];
    wire [5*16-1:0] in_user_metadata[NN];
    wire [5*16-1:0] out_user_metadata[NN];
    wire [5*4-1:0] in_error[NN];
    wire [5*4-1:0] out_error[NN];
    wire [5*2-1:0] in_epoch[NN];
    wire [5*2-1:0] out_epoch[NN];
    wire [4:0] event_input_accept[NN];
    wire [4:0] event_output_transfer[NN];
    wire [4:0] event_packet_head[NN];
    wire [4:0] event_packet_tail[NN];
    wire [4:0] event_input_stall[NN];
    wire [4:0] event_output_stall[NN];
    wire [4:0] event_vc_starved[NN];
    wire [4:0] event_credit_starved[NN];
    wire [4:0] event_route_error[NN];
    wire [4:0] event_protocol_error[NN];
    wire [4:0] event_parity_error[NN];
    wire [4:0] event_buffer_corrected[NN];
    wire [4:0] event_buffer_uncorrectable[NN];
    for (genvar n = 0; n < NN; n ++ ) begin : g_node
        localparam int X = n % MESH_X;
        localparam int Y = n / MESH_X;
        wire configured = i_config_valid && (&config_ready);
        noc_router #(.MESH_X(MESH_X), .MESH_Y(MESH_Y), .ROUTER_X(X), .ROUTER_Y(Y),
            .NUM_VCS(NUM_VCS), .FLOW_CONTROL(FLOW_CONTROL),
            .ROUTING_ALGORITHM(ROUTING_ALGORITHM), .ASYNC_RESET(ASYNC_RESET)) u_router (
            .i_clk(i_clk), .i_rstb(i_rstb), .i_drain(i_drain), .i_flush(i_flush),
            .i_error_clear(i_error_clear), .i_config_valid(configured),
            .o_config_ready(config_ready[n]), .o_config_accepted(config_accepted[n]),
            .o_config_rejected(config_rejected[n]),
            .i_config_port_enable(i_config_port_enable[n*5+:5]),
            .i_config_fault_port_mask(i_config_fault_port_mask[n*5+:5]),
            .i_in_valid(in_valid[n]), .o_in_ready(in_ready[n]), .i_in_parity(in_parity[n]),
            .o_out_valid(out_valid[n]), .i_out_ready(out_ready[n]), .o_out_parity(out_parity[n]),
            .i_in_data(in_data[n]),
            .o_out_data(out_data[n]),
            .i_in_keep(in_keep[n]),
            .o_out_keep(out_keep[n]),
            .i_in_head(in_head[n]),
            .o_out_head(out_head[n]),
            .i_in_tail(in_tail[n]),
            .o_out_tail(out_tail[n]),
            .i_in_fragment_index(in_fragment_index[n]),
            .o_out_fragment_index(out_fragment_index[n]),
            .i_in_vc(in_vc[n]),
            .o_out_vc(out_vc[n]),
            .i_in_source_node(in_source_node[n]),
            .o_out_source_node(out_source_node[n]),
            .i_in_source_endpoint(in_source_endpoint[n]),
            .o_out_source_endpoint(out_source_endpoint[n]),
            .i_in_destination_node(in_destination_node[n]),
            .o_out_destination_node(out_destination_node[n]),
            .i_in_destination_endpoint(in_destination_endpoint[n]),
            .o_out_destination_endpoint(out_destination_endpoint[n]),
            .i_in_context_id(in_context_id[n]),
            .o_out_context_id(out_context_id[n]),
            .i_in_message_type(in_message_type[n]),
            .o_out_message_type(out_message_type[n]),
            .i_in_traffic_class(in_traffic_class[n]),
            .o_out_traffic_class(out_traffic_class[n]),
            .i_in_packet_id(in_packet_id[n]),
            .o_out_packet_id(out_packet_id[n]),
            .i_in_stream_last(in_stream_last[n]),
            .o_out_stream_last(out_stream_last[n]),
            .i_in_user_metadata(in_user_metadata[n]),
            .o_out_user_metadata(out_user_metadata[n]),
            .i_in_error(in_error[n]),
            .o_out_error(out_error[n]),
            .i_in_epoch(in_epoch[n]),
            .o_out_epoch(out_epoch[n]),
            .i_out_credit_valid(credit_valid[n]), .i_out_credit_vc(credit_vc[n]),
            .i_out_credit_epoch(credit_epoch[n]), .o_in_credit_valid(return_valid[n]),
            .o_in_credit_vc(return_vc[n]), .o_in_credit_epoch(return_epoch[n]),
            .o_active_port_enable(o_active_port_enable[n*5+:5]),
            .o_active_fault_port_mask(o_active_fault_port_mask[n*5+:5]),
            .o_link_epoch(o_link_epoch[n*10+:10]),
            .o_input_vc_occupancy(o_input_vc_occupancy[n*5*NUM_VCS*2+:5*NUM_VCS*2]),
            .o_output_credit_count(o_output_credit_count[n*5*NUM_VCS*2+:5*NUM_VCS*2]),
            .o_input_packet_locked(o_input_packet_locked[n*5+:5]),
            .o_output_packet_locked(o_output_packet_locked[n*5+:5]),
            .o_idle(idle[n]), .o_quiescent(quiescent[n]), .o_drain_done(drain_done[n]),
            .o_flushed(flushed[n]), .o_error(error_flag[n]), .o_error_code(error_code[n]),
            .o_fatal_error(fatal[n]),
            .o_event_input_accept(event_input_accept[n]),
            .o_event_output_transfer(event_output_transfer[n]),
            .o_event_packet_head(event_packet_head[n]),
            .o_event_packet_tail(event_packet_tail[n]),
            .o_event_input_stall(event_input_stall[n]),
            .o_event_output_stall(event_output_stall[n]),
            .o_event_vc_starved(event_vc_starved[n]),
            .o_event_credit_starved(event_credit_starved[n]),
            .o_event_route_error(event_route_error[n]),
            .o_event_protocol_error(event_protocol_error[n]),
            .o_event_parity_error(event_parity_error[n]),
            .o_event_buffer_corrected(event_buffer_corrected[n]),
            .o_event_buffer_uncorrectable(event_buffer_uncorrectable[n])
        );
        assign o_event_input_accept[n] = event_input_accept[n][0];
        assign o_event_output_transfer[n] = event_output_transfer[n][0];
        assign o_event_packet_head[n] = event_packet_head[n][0];
        assign o_event_packet_tail[n] = event_packet_tail[n][0];
        assign o_event_input_stall[n] = (|event_input_stall[n]);
        assign o_event_output_stall[n] = (|event_output_stall[n]);
        assign o_event_vc_starved[n] = (|event_vc_starved[n]);
        assign o_event_credit_starved[n] = (|event_credit_starved[n]);
        assign o_event_route_error[n] = (|event_route_error[n]);
        assign o_event_protocol_error[n] = (|event_protocol_error[n]);
        assign o_event_parity_error[n] = (|event_parity_error[n]);
        assign o_event_buffer_corrected[n] = (|event_buffer_corrected[n]);
        assign o_event_buffer_uncorrectable[n] = (|event_buffer_uncorrectable[n]);
        assign in_valid[n][0] = i_in_valid[n];
        assign o_in_ready[n] = in_ready[n][0];
        assign in_parity[n][0] = i_in_parity[n];
        assign o_out_valid[n] = out_valid[n][0];
        assign out_ready[n][0] = i_out_ready[n];
        assign o_out_parity[n] = out_parity[n][0];
        assign credit_valid[n][0] = i_out_credit_valid[n];
        assign credit_vc[n][0+:VW] = i_out_credit_vc[n*VW+:VW];
        assign credit_epoch[n][0+:2] = i_out_credit_epoch[n*2+:2];
        assign o_in_credit_valid[n] = return_valid[n][0];
        assign o_in_credit_vc[n*VW+:VW] = return_vc[n][0+:VW];
        assign o_in_credit_epoch[n*2+:2] = return_epoch[n][0+:2];
        assign bridge_valid[n*5] = 1'b0;
        assign in_data[n][0+:32] = i_in_data[n*32+:32];
        assign o_out_data[n*32+:32] = out_data[n][0+:32];
        assign in_keep[n][0+:4] = i_in_keep[n*4+:4];
        assign o_out_keep[n*4+:4] = out_keep[n][0+:4];
        assign in_head[n][0+:1] = i_in_head[n*1+:1];
        assign o_out_head[n*1+:1] = out_head[n][0+:1];
        assign in_tail[n][0+:1] = i_in_tail[n*1+:1];
        assign o_out_tail[n*1+:1] = out_tail[n][0+:1];
        assign in_fragment_index[n][0+:4] = i_in_fragment_index[n*4+:4];
        assign o_out_fragment_index[n*4+:4] = out_fragment_index[n][0+:4];
        assign in_vc[n][0+:VW] = i_in_vc[n*VW+:VW];
        assign o_out_vc[n*VW+:VW] = out_vc[n][0+:VW];
        assign in_source_node[n][0+:8] = i_in_source_node[n*8+:8];
        assign o_out_source_node[n*8+:8] = out_source_node[n][0+:8];
        assign in_source_endpoint[n][0+:4] = i_in_source_endpoint[n*4+:4];
        assign o_out_source_endpoint[n*4+:4] = out_source_endpoint[n][0+:4];
        assign in_destination_node[n][0+:8] = i_in_destination_node[n*8+:8];
        assign o_out_destination_node[n*8+:8] = out_destination_node[n][0+:8];
        assign in_destination_endpoint[n][0+:4] = i_in_destination_endpoint[n*4+:4];
        assign o_out_destination_endpoint[n*4+:4] = out_destination_endpoint[n][0+:4];
        assign in_context_id[n][0+:8] = i_in_context_id[n*8+:8];
        assign o_out_context_id[n*8+:8] = out_context_id[n][0+:8];
        assign in_message_type[n][0+:4] = i_in_message_type[n*4+:4];
        assign o_out_message_type[n*4+:4] = out_message_type[n][0+:4];
        assign in_traffic_class[n][0+:3] = i_in_traffic_class[n*3+:3];
        assign o_out_traffic_class[n*3+:3] = out_traffic_class[n][0+:3];
        assign in_packet_id[n][0+:8] = i_in_packet_id[n*8+:8];
        assign o_out_packet_id[n*8+:8] = out_packet_id[n][0+:8];
        assign in_stream_last[n][0+:1] = i_in_stream_last[n*1+:1];
        assign o_out_stream_last[n*1+:1] = out_stream_last[n][0+:1];
        assign in_user_metadata[n][0+:16] = i_in_user_metadata[n*16+:16];
        assign o_out_user_metadata[n*16+:16] = out_user_metadata[n][0+:16];
        assign in_error[n][0+:4] = i_in_error[n*4+:4];
        assign o_out_error[n*4+:4] = out_error[n][0+:4];
        assign in_epoch[n][0+:2] = i_in_epoch[n*2+:2];
        assign o_out_epoch[n*2+:2] = out_epoch[n][0+:2];
        for (genvar p = 1; p < 5; p ++ ) begin : g_link
            localparam bit PRESENT = (p == 1 && Y > 0) || (p == 2 && X < MESH_X - 1) ||
                (p == 3 && Y < MESH_Y - 1) || (p == 4 && X > 0);
            localparam int PEER = p == 1 ? n - MESH_X : p == 2 ? n + 1 :
                p == 3 ? n + MESH_X : n - 1;
            localparam int REVERSE = p == 1 ? 3 : p == 2 ? 4 : p == 3 ? 1 : 2;
            if (PRESENT) begin : g_present
                wire [LW-1:0] source;
                wire [LW-1:0] received;
                wire presented = out_valid[PEER][REVERSE] && !i_flush;
                wire ready;
                wire valid;
                wire consume = i_flush || in_ready[n][p];
                assign source = {
                    out_data[PEER][REVERSE*32+:32],
                    out_keep[PEER][REVERSE*4+:4],
                    out_head[PEER][REVERSE*1+:1],
                    out_tail[PEER][REVERSE*1+:1],
                    out_fragment_index[PEER][REVERSE*4+:4],
                    out_vc[PEER][REVERSE*VW+:VW],
                    out_source_node[PEER][REVERSE*8+:8],
                    out_source_endpoint[PEER][REVERSE*4+:4],
                    out_destination_node[PEER][REVERSE*8+:8],
                    out_destination_endpoint[PEER][REVERSE*4+:4],
                    out_context_id[PEER][REVERSE*8+:8],
                    out_message_type[PEER][REVERSE*4+:4],
                    out_traffic_class[PEER][REVERSE*3+:3],
                    out_packet_id[PEER][REVERSE*8+:8],
                    out_stream_last[PEER][REVERSE*1+:1],
                    out_user_metadata[PEER][REVERSE*16+:16],
                    out_error[PEER][REVERSE*4+:4],
                    out_epoch[PEER][REVERSE*2+:2],
                    out_parity[PEER][REVERSE]
                };
                if (FLOW_CONTROL == 0) begin : g_ready
                    skid_buffer #(.DATA_WIDTH(LW), .ASYNC_RESET(ASYNC_RESET)) u_bridge (
                        .i_clk(i_clk), .i_rstb(i_rstb), .i_valid(presented), .o_ready(ready),
                        .i_data(source), .o_valid(valid), .i_ready(consume), .o_data(received)
                    );
                    assign bridge_valid[n*5+p] = valid;
                end else begin : g_credit
                    assign received = source;
                    assign ready = 1'b0;
                    assign valid = presented;
                    assign bridge_valid[n*5+p] = 1'b0;
                end
                assign in_valid[n][p] = valid && !i_flush;
                assign out_ready[PEER][REVERSE] = ready;
                assign credit_valid[PEER][REVERSE] = return_valid[n][p];
                assign credit_vc[PEER][REVERSE*VW+:VW] = return_vc[n][p*VW+:VW];
                assign credit_epoch[PEER][REVERSE*2+:2] = return_epoch[n][p*2+:2];
                assign {
                    in_data[n][p*32+:32],
                    in_keep[n][p*4+:4],
                    in_head[n][p*1+:1],
                    in_tail[n][p*1+:1],
                    in_fragment_index[n][p*4+:4],
                    in_vc[n][p*VW+:VW],
                    in_source_node[n][p*8+:8],
                    in_source_endpoint[n][p*4+:4],
                    in_destination_node[n][p*8+:8],
                    in_destination_endpoint[n][p*4+:4],
                    in_context_id[n][p*8+:8],
                    in_message_type[n][p*4+:4],
                    in_traffic_class[n][p*3+:3],
                    in_packet_id[n][p*8+:8],
                    in_stream_last[n][p*1+:1],
                    in_user_metadata[n][p*16+:16],
                    in_error[n][p*4+:4],
                    in_epoch[n][p*2+:2],
                    in_parity[n][p]
                } = received;
            end else begin : g_boundary
                assign in_valid[n][p] = 1'b0;
                assign in_parity[n][p] = 1'b0;
                assign out_ready[n][p] = 1'b0;
                assign credit_valid[n][p] = 1'b0;
                assign credit_vc[n][p*VW+:VW] = '0;
                assign credit_epoch[n][p*2+:2] = '0;
                assign bridge_valid[n*5+p] = 1'b0;
                assign in_data[n][p*32+:32] = '0;
                assign in_keep[n][p*4+:4] = '0;
                assign in_head[n][p*1+:1] = '0;
                assign in_tail[n][p*1+:1] = '0;
                assign in_fragment_index[n][p*4+:4] = '0;
                assign in_vc[n][p*VW+:VW] = '0;
                assign in_source_node[n][p*8+:8] = '0;
                assign in_source_endpoint[n][p*4+:4] = '0;
                assign in_destination_node[n][p*8+:8] = '0;
                assign in_destination_endpoint[n][p*4+:4] = '0;
                assign in_context_id[n][p*8+:8] = '0;
                assign in_message_type[n][p*4+:4] = '0;
                assign in_traffic_class[n][p*3+:3] = '0;
                assign in_packet_id[n][p*8+:8] = '0;
                assign in_stream_last[n][p*1+:1] = '0;
                assign in_user_metadata[n][p*16+:16] = '0;
                assign in_error[n][p*4+:4] = '0;
                assign in_epoch[n][p*2+:2] = '0;
            end
        end
    end
endmodule
