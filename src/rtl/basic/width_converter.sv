`timescale 1ns / 1ps

// Positional, single-owner stream conversion. Only complete narrow slices change
// order; units within a slice retain their bit/keep positions. Flush cancels the
// current item and must be authorized by the integrating stream/context policy.
module width_converter #(
    parameter IN_WIDTH = 32,
    parameter OUT_WIDTH = 128,
    parameter UNIT_WIDTH = 8,
    parameter USER_WIDTH = 1,
    parameter LSB_FIRST = 1,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((IN_WIDTH >= 1) === 1'b1) && (^IN_WIDTH !== 1'bx) &&
        ((OUT_WIDTH >= 1) === 1'b1) && (^OUT_WIDTH !== 1'bx) &&
        ((UNIT_WIDTH >= 1) === 1'b1) && (^UNIT_WIDTH !== 1'bx) &&
        ((USER_WIDTH >= 1) === 1'b1) && (^USER_WIDTH !== 1'bx) &&
        ((IN_WIDTH % UNIT_WIDTH == 0) === 1'b1) &&
        ((OUT_WIDTH % UNIT_WIDTH == 0) === 1'b1) &&
        (((IN_WIDTH >= OUT_WIDTH ? IN_WIDTH % OUT_WIDTH : OUT_WIDTH % IN_WIDTH) == 0) === 1'b1) &&
        ((LSB_FIRST === 0) || (LSB_FIRST === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)),
    localparam int unsigned INPUT_BITS = PARAMETERS_VALID ? IN_WIDTH : 1,
    localparam int unsigned OUTPUT_BITS = PARAMETERS_VALID ? OUT_WIDTH : 1,
    localparam int unsigned UNIT_BITS = PARAMETERS_VALID ? UNIT_WIDTH : 1,
    localparam int unsigned USER_BITS = PARAMETERS_VALID ? USER_WIDTH : 1,
    localparam int unsigned IN_UNITS = INPUT_BITS / UNIT_BITS,
    localparam int unsigned OUT_UNITS = OUTPUT_BITS / UNIT_BITS,
    localparam int unsigned NARROW_WIDTH = INPUT_BITS < OUTPUT_BITS ? INPUT_BITS : OUTPUT_BITS,
    localparam int unsigned WIDE_WIDTH = INPUT_BITS > OUTPUT_BITS ? INPUT_BITS : OUTPUT_BITS,
    localparam int unsigned RATIO = WIDE_WIDTH / NARROW_WIDTH,
    localparam int unsigned SLICE_INDEX_WIDTH = RATIO > 1 ? $clog2(RATIO) : 1
) (
    input  logic                   i_clk,
    input  logic                   i_rstb,
    input  logic                   i_flush,
    input  logic                   i_valid,
    output logic                   o_ready,
    input  logic [INPUT_BITS-1:0]   i_data,
    input  logic [IN_UNITS-1:0]     i_keep,
    input  logic                   i_last,
    input  logic [USER_BITS-1:0]    i_user,
    output logic                   o_valid,
    input  logic                   i_ready,
    output logic [OUTPUT_BITS-1:0]  o_data,
    output logic [OUT_UNITS-1:0]    o_keep,
    output logic                   o_last,
    output logic [USER_BITS-1:0]    o_user,
    output logic                   o_busy
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        width_converter_parameters_must_be_valid invalid_parameters ();
    end else begin : g_converter
        localparam int unsigned WIDE_UNITS = WIDE_WIDTH / UNIT_BITS;
        localparam int unsigned NARROW_UNITS = NARROW_WIDTH / UNIT_BITS;
        logic [WIDE_WIDTH-1:0] buffered_data;
        logic [WIDE_UNITS-1:0] buffered_keep;
        logic [USER_BITS-1:0] buffered_user;
        logic buffered_last;
        logic valid;
        wire enabled = i_rstb && !i_flush;
        wire accept_input = i_valid && o_ready;
        wire accept_output = o_valid && i_ready;
        wire [OUTPUT_BITS-1:0] selected_data;
        wire [OUT_UNITS-1:0] selected_keep;
        wire selected_last;

        assign o_valid = enabled && valid;
        assign o_last = o_valid && selected_last;

        operand_isolation #(.WIDTH(OUT_UNITS)) u_keep_clamp (
            .i_data(selected_keep),
            .i_isolate(!o_valid),
            .o_data(o_keep)
        );

        operand_isolation #(.WIDTH(USER_BITS)) u_user_clamp (
            .i_data(buffered_user),
            .i_isolate(!o_valid),
            .o_data(o_user)
        );

        for (genvar unit_index = 0; unit_index < OUT_UNITS; unit_index++) begin : g_output_unit
            operand_isolation #(.WIDTH(UNIT_BITS)) u_data_clamp (
                .i_data(selected_data[unit_index * UNIT_BITS +: UNIT_BITS]),
                .i_isolate(!o_valid || !selected_keep[unit_index]),
                .o_data(o_data[unit_index * UNIT_BITS +: UNIT_BITS])
            );
        end

        if (INPUT_BITS < OUTPUT_BITS) begin : g_pack
            logic [SLICE_INDEX_WIDTH-1:0] index;
            wire [SLICE_INDEX_WIDTH-1:0] physical_index;
            wire complete = i_last || index == SLICE_INDEX_WIDTH'(RATIO - 1);
            wire [WIDE_UNITS-1:0] previous_keep = index == '0 ? '0 : buffered_keep;
            logic [WIDE_UNITS-1:0] next_keep;

            if (LSB_FIRST == 1) begin : g_lsb_first
                assign physical_index = index;
            end else begin : g_msb_first
                assign physical_index = SLICE_INDEX_WIDTH'(RATIO - 1) - index;
            end

            assign o_ready = enabled && (!valid || i_ready);
            assign o_busy = enabled && (valid || index != '0);
            assign selected_data = buffered_data;
            assign selected_keep = buffered_keep;
            assign selected_last = buffered_last;

            // Completing a group returns the insertion index to zero. The old
            // output can be consumed while that zero-index group starts anew.
            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(i_flush || accept_input || accept_output),
                .i_d(!i_flush && accept_input && complete),
                .o_q(valid)
            );

            dff #(.WIDTH(SLICE_INDEX_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_index (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(i_flush || accept_input),
                .i_d(i_flush || complete ? {SLICE_INDEX_WIDTH{1'b0}} : index + 1'b1),
                .o_q(index)
            );

            always_comb begin
                next_keep = previous_keep;
                next_keep[physical_index * NARROW_UNITS +: NARROW_UNITS] = i_keep;
            end

            always_ff @(posedge i_clk) begin
                if (accept_input) begin
                    buffered_keep <= next_keep;
                    buffered_last <= i_last;
                    if (index == '0) buffered_user <= i_user;
                end
            end

            for (genvar unit_index = 0; unit_index < WIDE_UNITS; unit_index++) begin : g_input_unit
                // Invalid input units neither toggle storage nor leak through
                // keep clamping. Fresh keep state clears unfilled old slices.
                always_ff @(posedge i_clk) begin
                    if (accept_input && physical_index == SLICE_INDEX_WIDTH'(unit_index / NARROW_UNITS)
                            && i_keep[unit_index % NARROW_UNITS])
                        buffered_data[unit_index * UNIT_BITS +: UNIT_BITS] <=
                            i_data[(unit_index % NARROW_UNITS) * UNIT_BITS +: UNIT_BITS];
                end
            end
        end else begin : g_forward
            // Equal width has no slice index or terminal-search hardware.
            assign o_busy = o_valid;
            if (INPUT_BITS > OUTPUT_BITS) begin : g_unpack
                logic [SLICE_INDEX_WIDTH-1:0] index, terminal;
                logic [SLICE_INDEX_WIDTH-1:0] input_terminal;
                wire [SLICE_INDEX_WIDTH-1:0] physical_index;
                wire final_slice = index == terminal;

                if (LSB_FIRST == 1) begin : g_lsb_first
                    assign physical_index = index;
                end else begin : g_msb_first
                    assign physical_index = SLICE_INDEX_WIDTH'(RATIO - 1) - index;
                end
                // Search in stream order, retaining internal holes. An empty
                // last beat still emits sequence zero as an empty packet.
                always_comb begin
                    input_terminal = i_last ? '0 : SLICE_INDEX_WIDTH'(RATIO - 1);
                    for (int s = 0; s < RATIO; s++) begin
                        if (i_last && |i_keep[(LSB_FIRST == 1 ? s : RATIO - 1 - s) * NARROW_UNITS +: NARROW_UNITS])
                            input_terminal = SLICE_INDEX_WIDTH'(s);
                    end
                end

                assign o_ready = enabled && (!valid || (i_ready && final_slice));
                assign selected_data = buffered_data[physical_index * NARROW_WIDTH +: OUTPUT_BITS];
                assign selected_keep = buffered_keep[physical_index * NARROW_UNITS +: OUT_UNITS];
                assign selected_last = buffered_last && final_slice;

                dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_enable(i_flush || accept_input || (accept_output && final_slice)),
                    .i_d(!i_flush && accept_input),
                    .o_q(valid)
                );

                dff #(.WIDTH(SLICE_INDEX_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_index (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_enable(i_flush || accept_input || accept_output),
                    .i_d(i_flush || accept_input || final_slice ? {SLICE_INDEX_WIDTH{1'b0}} : index + 1'b1),
                    .o_q(index)
                );

                dff #(.WIDTH(SLICE_INDEX_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_terminal (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_enable(i_flush || accept_input),
                    .i_d(i_flush ? {SLICE_INDEX_WIDTH{1'b0}} : input_terminal),
                    .o_q(terminal)
                );
            end else begin : g_equal
                assign o_ready = enabled && (!valid || i_ready);
                assign selected_data = buffered_data;
                assign selected_keep = buffered_keep;
                assign selected_last = buffered_last;

                dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_enable(i_flush || accept_input || accept_output),
                    .i_d(!i_flush && accept_input),
                    .o_q(valid)
                );
            end

            always_ff @(posedge i_clk) begin
                if (accept_input) begin
                    buffered_keep <= i_keep;
                    buffered_last <= i_last;
                    buffered_user <= i_user;
                end
            end

            for (genvar unit_index = 0; unit_index < WIDE_UNITS; unit_index++) begin : g_input_unit
                always_ff @(posedge i_clk) begin
                    if (accept_input && i_keep[unit_index])
                        buffered_data[unit_index * UNIT_BITS +: UNIT_BITS] <=
                            i_data[unit_index * UNIT_BITS +: UNIT_BITS];
                end
            end
        end
    end
endmodule
