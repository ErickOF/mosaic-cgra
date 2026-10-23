"""Generate the parameterized mesh fixture with real routers and registered ready links."""

from pathlib import Path

FIELDS = dict(
    data='32',
    keep='4',
    head='1',
    tail='1',
    fragment_index='4',
    vc='VW',
    source_node='8',
    source_endpoint='4',
    destination_node='8',
    destination_endpoint='4',
    context_id='8',
    message_type='4',
    traffic_class='3',
    packet_id='8',
    stream_last='1',
    user_metadata='16',
    error='4',
    epoch='2',
)
EVENTS = (
    'input_accept',
    'output_transfer',
    'packet_head',
    'packet_tail',
    'input_stall',
    'output_stall',
    'vc_starved',
    'credit_starved',
    'route_error',
    'protocol_error',
    'parity_error',
    'buffer_corrected',
    'buffer_uncorrectable',
)


def render():
    text = """`timescale 1ns / 1ps

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
"""
    for name, w in FIELDS.items():
        text += f'    input logic [NN*{w}-1:0] i_in_{name},\n'
    text += """    input logic [NN-1:0] i_in_parity,
    output wire [NN-1:0] o_out_valid,
    input logic [NN-1:0] i_out_ready,
"""
    for name, w in FIELDS.items():
        text += f'    output wire [NN*{w}-1:0] o_out_{name},\n'
    text += """    output wire [NN-1:0] o_out_parity,
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
"""
    text += ',\n'.join(f'    output wire [NN-1:0] o_event_{name}' for name in EVENTS)
    text += """
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
"""
    for name, w in FIELDS.items():
        text += f'    wire [5*{w}-1:0] in_{name}[NN];\n'
        text += f'    wire [5*{w}-1:0] out_{name}[NN];\n'
    for name in EVENTS:
        text += f'    wire [4:0] event_{name}[NN];\n'
    text += """    for (genvar n = 0; n < NN; n ++ ) begin : g_node
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
"""
    for name in FIELDS:
        text += f'            .i_in_{name}(in_{name}[n]),\n'
        text += f'            .o_out_{name}(out_{name}[n]),\n'
    text += """            .i_out_credit_valid(credit_valid[n]), .i_out_credit_vc(credit_vc[n]),
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
"""
    text += (
        ',\n'.join(f'            .o_event_{name}(event_{name}[n])' for name in EVENTS)
        + '\n        );\n'
    )
    for name in EVENTS:
        value = (
            f'event_{name}[n][0]'
            if name in ('input_accept', 'output_transfer', 'packet_head', 'packet_tail')
            else f'(|event_{name}[n])'
        )
        text += f'        assign o_event_{name}[n] = {value};\n'
    text += """        assign in_valid[n][0] = i_in_valid[n];
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
"""
    for name, w in FIELDS.items():
        text += f'        assign in_{name}[n][0+:{w}] = i_in_{name}[n*{w}+:{w}];\n'
        text += f'        assign o_out_{name}[n*{w}+:{w}] = out_{name}[n][0+:{w}];\n'
    text += """        for (genvar p = 1; p < 5; p ++ ) begin : g_link
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
"""
    text += ',\n'.join(
        f'                    out_{f}[PEER][REVERSE*{w}+:{w}]' for f, w in FIELDS.items()
    )
    text += ',\n                    out_parity[PEER][REVERSE]\n                };\n'
    text += """                if (FLOW_CONTROL == 0) begin : g_ready
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
"""
    text += ',\n'.join(f'                    in_{f}[n][p*{w}+:{w}]' for f, w in FIELDS.items())
    text += ',\n                    in_parity[n][p]\n                } = received;\n'
    text += """            end else begin : g_boundary
                assign in_valid[n][p] = 1'b0;
                assign in_parity[n][p] = 1'b0;
                assign out_ready[n][p] = 1'b0;
                assign credit_valid[n][p] = 1'b0;
                assign credit_vc[n][p*VW+:VW] = '0;
                assign credit_epoch[n][p*2+:2] = '0;
                assign bridge_valid[n*5+p] = 1'b0;
"""
    for f, w in FIELDS.items():
        text += f"                assign in_{f}[n][p*{w}+:{w}] = '0;\n"
    text += """            end
        end
    end
endmodule
"""
    return text


if __name__ == '__main__':
    Path(__file__).with_name('noc_router_mesh_tb.sv').write_text(render(), encoding='utf-8')
