`timescale 1ns / 1ps
`default_nettype none
// Convert physical link slots to input capture slots and check hop consistency.
// Queued boundary ingress and egress each add exactly one published stage.
module predicate_network_schedule #(
    parameter int N = 16,
    parameter int I = 5,
    parameter int O = 5,
    parameter int TX = 1,
    parameter int RX = 1,
    parameter int IL = 48,
    parameter int L = 48,
    parameter int LB = 48,
    parameter int LX = 6,
    parameter int PM = 256,
    parameter int PW = 9,
    parameter int S = 3,
    parameter int RI = 320
) (
    input wire [RI-1:0] i_route,
    input wire [LB-1:0] i_enable,
    input wire [LB*PM-1:0] i_slots,
    input wire [PW-1:0] i_period,
    input wire [N*I*LX-1:0] i_inputs,
    input wire [N*O*LX-1:0] i_outputs,
    output logic [N*I*PM-1:0] o_input_slots,
    output logic [N*I-1:0] o_checked,
    output logic o_bad
);
    always @* begin
        o_input_slots = '0;
        o_checked = '0;
        o_bad = 1'b0;

        if (i_period > 0 && i_period <= PM && i_enable != 0) begin
            for (int u = 0; u < N * I; u++) begin
                int link_id;
                int shift;
                logic selected;
                link_id = int'(i_inputs[u*LX+:LX]);
                selected = 1'b0;
                shift = 0;

                if (u % I >= TX && link_id < L && i_enable[link_id]) begin
                    selected = 1'b1;
                    shift = link_id < IL ? 0 : -1;
                end else begin
                    for (int o = O - 1; o >= RX; o--) begin
                        int outgoing;
                        outgoing = int'(i_outputs[(u/I*O+o)*LX+:LX]);
                        if (i_route[u/I*O+o] && i_route[N*O+(u/I*O+o)*S+:S] == S'(u % I) &&
                            outgoing < L && i_enable[outgoing]) begin
                            selected = 1'b1;
                            link_id = outgoing;
                            shift = outgoing < IL ? 1 : 2;
                        end
                    end
                end

                o_checked[u] = selected;

                if (selected) begin
                    for (int t = 0; t < PM; t++) begin
                        if (t < i_period) o_input_slots[u*PM+t] =
                            i_slots[link_id*PM+(t+shift+int'(i_period))%int'(i_period)];
                    end

                    for (int o = RX; o < O; o++) begin
                        int outgoing;
                        outgoing = int'(i_outputs[(u/I*O+o)*LX+:LX]);

                        if (i_route[u/I*O+o] && i_route[N*O+(u/I*O+o)*S+:S] == S'(u % I) &&
                            outgoing < L && i_enable[outgoing]) begin

                            for (int t = 0; t < PM; t++)
                                if (t < i_period && o_input_slots[u*PM+t] !=
                                    i_slots[outgoing*PM+(t+(outgoing<IL ? 1 : 2))%i_period])
                                    o_bad = 1'b1;
                        end
                    end
                end
            end
        end
    end
endmodule
`default_nettype wire
