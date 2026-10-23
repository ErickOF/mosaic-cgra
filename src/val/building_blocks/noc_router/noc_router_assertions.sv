`timescale 1ns / 1ps

// Native, verification-only invariants complement the independent Python packet
// ledger. Observe real handshakes before NBA and registered events one tick later.
module noc_router_assertions #(
    parameter int V = 2,
    parameter int DEPTH = 2,
    parameter int CREDITS = 2,
    parameter int FLOW = 1,
    parameter int FW = 114,
    parameter int E = 2,
    localparam int VW = V > 1 ? $clog2(V) : 1,
    localparam int OCC = $clog2(DEPTH + 1),
    localparam int CW = $clog2(CREDITS + 1)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_integrity_bad,
    input logic i_fatal,
    input logic [4:0] i_out_ready,
    input logic [4:0] o_out_valid,
    input logic [5*FW-1:0] i_observed_output,
    input logic [5*VW-1:0] o_out_vc,
    input logic [5*V*CW-1:0] o_output_credit_count,
    input logic [5*V*OCC-1:0] o_input_vc_occupancy,
    input logic [5*V-1:0] i_pops,
    input logic [4:0] i_switch,
    input logic [14:0] i_owner,
    input logic [5*VW-1:0] i_selected_vc,
    input logic [4:0] o_in_credit_valid,
    input logic [5*VW-1:0] o_in_credit_vc
);
    logic [4:0] held = '0;
    logic [5*FW-1:0] previous;
    bit armed = 1'b0;
    logic [4:0] expected_credit;
    logic [5*VW-1:0] expected_vc;
    always @(posedge i_clk) begin
        if (!i_rstb) begin
            held = '0;
            armed = 1'b1;
        end else if (armed) begin
            expected_credit = '0;
            expected_vc = '0;
            for (int p = 0; p < 5; p++) begin
                int pop_count;
                pop_count = 0;
                for (int v = 0; v < V; v++)
                    if (i_pops[p*V+v]) pop_count++;
                assert (( ^ i_pops !== 1'bx) && pop_count <= 1)
                else $fatal(1, "NOC_HDL: multiple or unknown input FIFO pops");
                if (!i_flush && !i_fatal && !i_integrity_bad && held[p]) begin
                    assert (o_out_valid[p] &&
                        previous[p*FW+:FW] === i_observed_output[p*FW+:FW])
                    else $fatal(1, "NOC_HDL: stalled output changed");
                end
                if (!o_out_valid[p]) begin
                    assert (i_observed_output[p*FW+:FW] === {FW{1'b0}})
                    else $fatal(1, "NOC_HDL: invalid output was not clamped");
                end
                held[p] = FLOW == 0 && o_out_valid[p] && !i_out_ready[p] && !i_flush;
                previous[p*FW+:FW] = i_observed_output[p*FW+:FW];
                for (int v = 0; v < V; v++) begin
                    assert (32'(o_input_vc_occupancy[(p*V+v)*OCC+:OCC]) <= DEPTH)
                    else $fatal(1, "NOC_HDL: input FIFO capacity");
                    if (FLOW == 1) begin
                        assert (32'(o_output_credit_count[(p*V+v)*CW+:CW]) <= CREDITS)
                        else $fatal(1, "NOC_HDL: output credit capacity");
                        if (i_pops[p*V+v]) begin
                            expected_credit[p] = 1'b1;
                            expected_vc[p*VW+:VW] = VW'(v);
                        end
                    end
                end
                if (FLOW == 1 && o_out_valid[p]) begin
                    assert (32'(o_out_vc[p*VW+:VW]) < V)
                    else $fatal(1, "NOC_HDL: output VC range");
                    assert (o_output_credit_count[(p*V+int'(o_out_vc[p*VW+:VW]))*CW+:CW] != 0)
                    else $fatal(1, "NOC_HDL: launch with zero credit");
                end
                if (i_switch[p]) begin
                    assert (32'(i_owner[p*3+:3]) < 5 &&
                        32'(i_selected_vc[p*VW+:VW]) < V)
                    else $fatal(1, "NOC_HDL: switch ownership range");
                    assert (i_pops[int'(i_owner[p*3+:3])*V+int'(i_selected_vc[p*VW+:VW])])
                    else $fatal(1, "NOC_HDL: switch transfer without FIFO pop");
                end
            end
            if (i_flush) begin
                assert (o_out_valid == 0 && i_pops == 0 && i_switch == 0)
                else $fatal(1, "NOC_HDL: transfer during flush");
                expected_credit = '0;
                expected_vc = '0;
                held = '0;
            end
            #1ps;
            assert (o_in_credit_valid === expected_credit && o_in_credit_vc === expected_vc)
            else $fatal(1, "NOC_HDL: input credit does not correspond to FIFO pop");
        end
    end
endmodule
