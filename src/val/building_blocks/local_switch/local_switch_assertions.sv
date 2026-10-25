`timescale 1ns / 1ps

// Simulation safety checks. Producer persistence and consumer fairness are
// environment contracts and are checked separately from implementation safety.
module local_switch_assertions #(
    parameter int I = 4,
    parameter int O = 4,
    parameter int D = 128,
    parameter int M = 32,
    parameter int C = 8,
    parameter int S = 2,
    parameter int ASYNC_RESET = 0,
    localparam int E = 4 * I + 2 * O + 3,
    localparam int R = O + O * S + C
) (
    input wire i_clk,
    input wire i_rstb,
    input wire run,
    input wire flush,
    input wire traffic,
    input wire config_good,
    input wire config_bad,
    input wire config_accept,
    input wire [I-1:0] buffered,
    input wire [I*O-1:0] pending,
    input wire [I*O-1:0] destinations,
    input wire [I-1:0] input_accept,
    input wire [O-1:0] output_transfer,
    input wire [I-1:0] item_complete,
    input wire [I-1:0] multicast_accept,
    input wire [I-1:0] input_stall,
    input wire [O-1:0] output_stall,
    input wire [2:0] state_error,
    input wire [O-1:0] o_active_output_enable,
    input wire [O*S-1:0] o_active_output_select,
    input wire [C-1:0] o_active_context_id,
    input wire [O-1:0] i_config_output_enable,
    input wire [O*S-1:0] i_config_output_select,
    input wire [C-1:0] i_config_context_id,
    input wire [I-1:0] o_input_ready,
    input wire [O-1:0] o_output_valid,
    input wire [O*D-1:0] o_output_data,
    input wire [O*M-1:0] o_output_metadata,
    input wire o_idle,
    input wire o_quiescent,
    input wire [E-1:0] events
);
    integer copies;
    bit initialized = 0;
    logic [E-1:0] expected_events;
    logic [R-1:0] expected_routes;

    always @(negedge i_rstb) begin
        if (ASYNC_RESET && (i_rstb === 1'b0)) begin
            copies = 0;
            expected_events = '0;
            expected_routes = '0;
            initialized = 1;
        end
    end

    always @(posedge i_clk) begin
        if (i_rstb === 1'b0) begin
            copies = 0;
            initialized = 1;
            expected_events = '0;
            expected_routes = '0;
        end else if (run && initialized) begin
            expected_routes = config_good ? {i_config_output_enable,
                i_config_output_select, i_config_context_id} : {o_active_output_enable,
                o_active_output_select, o_active_context_id};
            expected_events = {config_good, config_bad, flush&&!o_idle,
                input_accept, output_transfer, input_stall, output_stall,
                multicast_accept, item_complete};
            if (config_accept)
                assert (o_quiescent && o_input_ready == '0 && o_output_valid == '0)
                    else $fatal(1, "Configuration was not atomic");
            if (state_error != 0 || flush)
                assert (o_input_ready == '0 && o_output_valid == '0)
                    else $fatal(1, "Corrupt or flushed switch exposed traffic");
            if (flush) copies = 0;
            else if (state_error == 0) begin
                for (int i = 0; i < I; i++) begin
                    if (input_accept[i]) begin
                        assert (traffic && ( | destinations[i*O+:O]))
                            else $fatal(1, "Unrouted source accepted an item");
                        // Count bits explicitly: Icarus widens a dynamic slice
                        // passed directly to $countones in this procedural loop.
                        for (int o = 0; o < O; o++)
                            if (destinations[i*O+o]) copies++;
                    end
                    if (item_complete[i])
                        assert (buffered[i] && ( | pending[i*O+:O]) &&
                            (pending[i*O+:O] & ~output_transfer) == '0)
                            else $fatal(1, "Item completed before final copy");
                end
                copies -= $countones(output_transfer);
            end
            for (int o = 0; o < O; o++) begin
                if (!o_output_valid[o])
                    assert (o_output_data[o*D+:D] === {D{1'b0}} &&
                        o_output_metadata[o*M+:M] === {M{1'b0}})
                        else $fatal(1, "Invalid output leaked a payload");
            end
        end
        #1ps;
        if (initialized && (i_rstb === 1'b0 || run)) begin
            assert (events == expected_events) else $fatal(1, "Incorrect switch event pulse");
            assert ({o_active_output_enable, o_active_output_select,
                o_active_context_id} == expected_routes)
                else $fatal(1, "Unexpected active route update");
            if (state_error == 0) begin
                assert (copies >= 0 && copies == $countones(pending))
                    else $fatal(1, "Multicast copy conservation: ledger=%0d pending=%h count=%0d",
                        copies, pending, $countones(pending));
                for (int i = 0; i < I; i++) begin
                    assert (buffered[i] == ( | pending[i*O+:O]))
                        else $fatal(1, "Input occupancy disagrees with pending copies");
                    assert ((pending[i*O+:O] & ~destinations[i*O+:O]) == '0)
                        else $fatal(1, "Copy pending for an inactive route");
                end
            end
        end
    end
endmodule
