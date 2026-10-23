`timescale 1ns / 1ps
`default_nettype none

// Small flip-flop predicate file. Reads use pre-edge state, while per-lane
// writeback and the complete response commit together on each enabled edge.
module predicate_unit #(
    parameter PRED_DEPTH = 4,
    parameter NUM_LANES = 4,
    parameter ASYNC_RESET = 0,
    parameter OPCODE_WIDTH = 4,
    localparam bit PARAMETERS_VALID =
        ((PRED_DEPTH >= 1 && PRED_DEPTH <= 1073741823) === 1'b1) &&
        (^PRED_DEPTH !== 1'bx) &&
        ((NUM_LANES >= 1 && NUM_LANES <= 715827880) === 1'b1) &&
        (^NUM_LANES !== 1'bx) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) && (OPCODE_WIDTH === 4) &&
        ((128'(PRED_DEPTH) * 128'(NUM_LANES) * 2 < 128'd2147483647) === 1'b1),
    localparam int D = PARAMETERS_VALID ? PRED_DEPTH : 1,
    localparam int N = PARAMETERS_VALID ? NUM_LANES : 1,
    localparam int ADDR_WIDTH = D > 1 ? $clog2(D) : 1
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [3:0] i_opcode,
    input logic [N-1:0] i_lane_mask,
    input logic [ADDR_WIDTH-1:0] i_source_a_addr,
    input logic [ADDR_WIDTH-1:0] i_source_b_addr,
    input logic [ADDR_WIDTH-1:0] i_destination_addr,
    input logic [N-1:0] i_predicate_input,
    input logic i_write_enable,
    output wire o_valid,
    output wire [N-1:0] o_result,
    output wire [N-1:0] o_result_valid,
    output wire o_any,
    output wire o_all,
    output wire [N-1:0] o_updated_mask,
    output wire o_invalidated,
    output wire o_illegal_operation
);
    import predicate_unit_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        predicate_unit_parameters_must_be_valid invalid_parameters ();
    end else begin : g_predicate
        // Parameter-dependent response fields stay local to the implementation.
        typedef struct packed {
            logic valid;
            logic [N-1:0] result;
            logic [N-1:0] result_valid;
            logic any_bit;
            logic all_bits;
            logic [N-1:0] updated_mask;
            logic invalidated;
            logic illegal;
        } response_t;

        wire [D-1:0][N-1:0] predicate_data;
        wire [D-1:0][N-1:0] predicate_valid;
        wire controls_known = (^{i_opcode, i_lane_mask, i_write_enable} !== 1'bx);
        wire fire = i_rstb === 1'b1 && i_clock_enable === 1'b1 && i_valid === 1'b1;
        wire nonempty = controls_known && (|i_lane_mask);
        wire opcode_known = controls_known && i_opcode <= PRED_INVALIDATE;
        wire need_a = opcode_known && i_opcode >= PRED_PASS_A && i_opcode <= PRED_XOR;
        wire need_b = opcode_known && i_opcode >= PRED_AND && i_opcode <= PRED_XOR;
        wire read_enable = fire && nonempty;
        wire [ADDR_WIDTH-1:0] source_addr[2];
        wire [1:0] source_needed = {need_b, need_a};
        wire [1:0] source_address_valid;
        wire [N-1:0] source_data[2];
        wire [N-1:0] source_valid[2];
        wire [D-1:0] destination_decoded;
        wire destination_valid;

        assign source_addr[0] = i_source_a_addr;
        assign source_addr[1] = i_source_b_addr;

        for (genvar port = 0; port < 2; port++) begin : g_read
            wire [D-1:0] decoded;
            wire [N-1:0] lane_data[D];
            wire [N-1:0] lane_valid[D];
            logic [N-1:0] selected_data;
            logic [N-1:0] selected_valid;

            decoder #(.NUM_OUTPUTS(D)) u_decoder (
                .i_enable(read_enable && source_needed[port]),
                .i_select(source_addr[port]),
                .o_decoded(decoded),
                .o_select_valid(source_address_valid[port])
            );

            // Gate before read reduction: unselected entries, unused ports and
            // masked lanes cannot switch the active Boolean operand cone.
            for (genvar entry = 0; entry < D; entry++) begin : g_entry
                for (genvar lane = 0; lane < N; lane++) begin : g_lane
                    operand_isolation #(.WIDTH(2)) u_read (
                        .i_data({predicate_data[entry][lane], predicate_valid[entry][lane]}),
                        .i_isolate(!(decoded[entry] && i_lane_mask[lane])),
                        .o_data({lane_data[entry][lane], lane_valid[entry][lane]})
                    );
                end
            end

            always_comb begin
                selected_data = '0;
                selected_valid = '0;

                for (int entry = 0; entry < D; entry++) begin
                    selected_data = selected_data | lane_data[entry];
                    selected_valid = selected_valid | lane_valid[entry];
                end
            end

            assign source_data[port] = selected_data;
            assign source_valid[port] = selected_valid;
        end

        decoder #(.NUM_OUTPUTS(D)) u_destination (
            .i_enable(fire && nonempty && opcode_known && i_write_enable),
            .i_select(i_destination_addr),
            .o_decoded(destination_decoded),
            .o_select_valid(destination_valid)
        );

        // Empty masks ignore all addresses and validity. All other requirements
        // are resolved before enabling even one destination bit (atomic failure).
        wire sources_legal = !nonempty ||
            ((!need_a || (source_address_valid[0] && source_valid[0] == i_lane_mask)) &&
            (!need_b || (source_address_valid[1] && source_valid[1] == i_lane_mask)));
        wire legal = opcode_known && sources_legal &&
            (!nonempty || !i_write_enable || destination_valid) &&
            (i_opcode != PRED_INVALIDATE || i_write_enable);
        wire invalidate = i_opcode == PRED_INVALIDATE;
        wire [N-1:0] external_data;

        for (genvar lane = 0; lane < N; lane++) begin : g_external
            operand_isolation #(.WIDTH(1)) u_input (
                .i_data(i_predicate_input[lane]),
                .i_isolate(!(fire && legal && i_opcode == PRED_LOAD && i_lane_mask[lane])),
                .o_data(external_data[lane])
            );
        end

        wire [N-1:0] active_mask = fire && legal ? i_lane_mask : '0;
        logic [N-1:0] generated;
        response_t request;
        response_t response;

        always_comb begin
            generated = '0;

            case (i_opcode)
                PRED_SET: generated = active_mask;
                PRED_LOAD: generated = external_data;
                PRED_PASS_A: generated = source_data[0];
                PRED_NOT_A: generated = ~source_data[0] & active_mask;
                PRED_AND: generated = source_data[0] & source_data[1];
                PRED_OR: generated = source_data[0] | source_data[1];
                PRED_XOR: generated = source_data[0] ^ source_data[1];
                default: generated = '0;
            endcase

            request = '0;

            if (i_valid === 1'b1) begin
                request.valid = 1'b1;
                request.illegal = !legal;

                if (legal) begin
                    request.updated_mask = i_write_enable ? i_lane_mask : '0;
                    request.invalidated = invalidate;

                    if (!invalidate) begin
                        request.result = generated;
                        request.result_valid = i_lane_mask;
                        request.any_bit = |generated;
                        request.all_bits = (|i_lane_mask) && generated == i_lane_mask;
                    end
                end
            end
        end

        for (genvar entry = 0; entry < D; entry++) begin : g_entry
            for (genvar lane = 0; lane < N; lane++) begin : g_lane
                wire update_lane;
                wire unused_suppressed;

                write_gate u_write (
                    .i_write_enable(destination_decoded[entry] && i_lane_mask[lane]),
                    .i_suppress(!legal),
                    .o_write_enable(update_lane),
                    .o_write_suppressed(unused_suppressed)
                );

                // Data is deliberately unreset. Validity excludes stale data;
                // invalidation holds the physical data bit and clears validity.
                dff #(.WIDTH(1)) u_data (
                    .i_clk(i_clk),
                    .i_rstb(1'b1),
                    .i_enable(update_lane && !invalidate),
                    .i_d(generated[lane]),
                    .o_q(predicate_data[entry][lane])
                );

                dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_enable(update_lane),
                    .i_d(!invalidate),
                    .o_q(predicate_valid[entry][lane])
                );
            end
        end

        dff #(.WIDTH($bits(response_t)), .ASYNC_RESET(ASYNC_RESET != 0)) u_response (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(i_clock_enable),
            .i_d(request),
            .o_q(response)
        );

        assign {o_valid, o_result, o_result_valid, o_any, o_all, o_updated_mask,
            o_invalidated, o_illegal_operation} = response;

`ifdef MOSAIC_PREDICATE_UNIT_FORMAL
        predicate_unit_formal #(
            .D(D),
            .N(N),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_formal (
            .actual_data(predicate_data),
            .actual_valid(predicate_valid),
            .*
        );
`endif
`ifdef MOSAIC_PREDICATE_UNIT_ASSERTIONS
        predicate_unit_assertions #(.D(D), .N(N), .ASYNC_RESET(ASYNC_RESET)) u_assertions (
            .actual_data(predicate_data),
            .actual_valid(predicate_valid),
            .*
        );
`endif
    end
endmodule
`default_nettype wire
