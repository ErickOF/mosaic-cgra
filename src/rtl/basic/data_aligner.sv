`timescale 1ns / 1ps

// Translate a two-word byte window; bytes leaving either edge are explicit
// spill. Byte zero is the least-significant byte at the lowest address.
module data_aligner #(
    // Preserve negative, oversized and X/Z arguments for the elaboration guard.
    parameter DATA_WIDTH = 128,
    parameter USER_WIDTH = 1,
    parameter SUPPORT_SHIFT_LOW = 1,
    parameter SUPPORT_SHIFT_HIGH = 1,
    parameter REGISTER_OUTPUTS = 0,
    parameter ASYNC_RESET = 0,
    localparam int unsigned WORD_BYTES = (^DATA_WIDTH !== 1'bx) && DATA_WIDTH >= 8 && DATA_WIDTH % 8 == 0 ? DATA_WIDTH / 8 : 1,
    localparam int unsigned OFFSET_WIDTH = WORD_BYTES > 1 ? $clog2(WORD_BYTES) : 1,
    localparam int unsigned WINDOW_BYTES = 2 * WORD_BYTES,
    localparam int unsigned DATA_BITS = 8 * WORD_BYTES,
    localparam int unsigned USER_BITS = (^USER_WIDTH !== 1'bx) && USER_WIDTH >= 1 ? USER_WIDTH : 1
) (
    input  logic i_clk,
    input  logic i_rstb,
    input  logic i_flush,
    input  logic i_valid,
    output logic o_ready,
    input  logic [DATA_BITS-1:0] i_data_lo,
    input  logic [WORD_BYTES-1:0] i_strb_lo,
    input  logic [DATA_BITS-1:0] i_data_hi,
    input  logic [WORD_BYTES-1:0] i_strb_hi,
    input  logic [OFFSET_WIDTH-1:0] i_offset,
    input  logic i_shift_high,
    input  logic i_last,
    input  logic [USER_BITS-1:0] i_user,
    output logic o_valid,
    input  logic i_ready,
    output logic [DATA_BITS-1:0] o_data_lo,
    output logic [WORD_BYTES-1:0] o_strb_lo,
    output logic [DATA_BITS-1:0] o_data_hi,
    output logic [WORD_BYTES-1:0] o_strb_hi,
    output logic [DATA_BITS-1:0] o_spill_data,
    output logic [WORD_BYTES-1:0] o_spill_strb,
    output logic o_spill_high,
    output logic o_unaligned,
    output logic o_split,
    output logic o_last,
    output logic [USER_BITS-1:0] o_user,
    output logic o_config_error,
    output logic o_busy
);
    localparam bit PARAMETERS_VALID =
        (^DATA_WIDTH !== 1'bx) && DATA_WIDTH >= 8 && DATA_WIDTH % 8 == 0 &&
        (^USER_WIDTH !== 1'bx) && USER_WIDTH >= 1 &&
        (SUPPORT_SHIFT_LOW === 0 || SUPPORT_SHIFT_LOW === 1) &&
        (SUPPORT_SHIFT_HIGH === 0 || SUPPORT_SHIFT_HIGH === 1) &&
        (SUPPORT_SHIFT_LOW === 1 || SUPPORT_SHIFT_HIGH === 1) &&
        (REGISTER_OUTPUTS === 0 || REGISTER_OUTPUTS === 1) &&
        (ASYNC_RESET === 0 || ASYNC_RESET === 1);

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        data_aligner_parameters_must_be_valid invalid_parameters ();
    end else begin : g_aligner
        localparam int unsigned RESULT_WIDTH = 3 * DATA_BITS + 3 * WORD_BYTES + 4 + USER_BITS;
        wire [WINDOW_BYTES-1:0] input_strobe = {i_strb_hi, i_strb_lo};
        wire [2*DATA_BITS-1:0] input_data = {i_data_hi, i_data_lo};
        wire [2*DATA_BITS-1:0] isolated_data;
        wire [3*DATA_BITS-1:0] translated_data;
        wire [3*WORD_BYTES-1:0] translated_strobe;
        wire direction_supported;

        // Isolation precedes the shifters, including when unstrobed bytes are
        // X/Z. Invalid windows cannot switch the data-alignment cone either.
        for (genvar lane = 0; lane < WINDOW_BYTES; lane++) begin : g_byte
            operand_isolation #(.WIDTH(8)) u_isolate (
                .i_data(input_data[8*lane+:8]),
                .i_isolate(!(i_valid & input_strobe[lane])),
                .o_data(isolated_data[8*lane+:8])
            );
        end

        // Normalize each direction to {spill, high word, low word}. Extra zero
        // lanes retain every translated byte without arithmetic shifts or wrap.
        if (SUPPORT_SHIFT_LOW == 1 && SUPPORT_SHIFT_HIGH == 1) begin : g_both
            wire [3*DATA_BITS-1:0] shifted_low = {isolated_data, {DATA_BITS{1'b0}}} >> {i_offset, 3'b000};
            wire [3*WORD_BYTES-1:0] strobe_low = {input_strobe, {WORD_BYTES{1'b0}}} >> i_offset;
            wire [3*DATA_BITS-1:0] shifted_high = {{DATA_BITS{1'b0}}, isolated_data} << {i_offset, 3'b000};
            wire [3*WORD_BYTES-1:0] strobe_high = {{WORD_BYTES{1'b0}}, input_strobe} << i_offset;
            assign translated_data = i_shift_high ? shifted_high :
                {shifted_low[DATA_BITS-1:0], shifted_low[3*DATA_BITS-1:DATA_BITS]};
            assign translated_strobe = i_shift_high ? strobe_high :
                {strobe_low[WORD_BYTES-1:0], strobe_low[3*WORD_BYTES-1:WORD_BYTES]};
            // Keep unknown direction encodings observable in simulation.
            assign direction_supported = i_shift_high | !i_shift_high;
        end else if (SUPPORT_SHIFT_LOW == 1) begin : g_low
            wire [3*DATA_BITS-1:0] shifted = {isolated_data, {DATA_BITS{1'b0}}} >> {i_offset, 3'b000};
            wire [3*WORD_BYTES-1:0] strobe = {input_strobe, {WORD_BYTES{1'b0}}} >> i_offset;
            assign translated_data = {shifted[DATA_BITS-1:0], shifted[3*DATA_BITS-1:DATA_BITS]};
            assign translated_strobe = {strobe[WORD_BYTES-1:0], strobe[3*WORD_BYTES-1:WORD_BYTES]};
            assign direction_supported = !i_shift_high;
        end else begin : g_high
            assign translated_data = {{DATA_BITS{1'b0}}, isolated_data} << {i_offset, 3'b000};
            assign translated_strobe = {{WORD_BYTES{1'b0}}, input_strobe} << i_offset;
            assign direction_supported = i_shift_high;
        end

        wire running = i_rstb & !i_flush;
        wire configuration_ok = ({1'b0, i_offset} < (OFFSET_WIDTH + 1)'(WORD_BYTES)) & direction_supported;
        // Configuration errors describe valid input requests. Idle controls do
        // not obstruct readiness; an old registered result may always drain.
        assign o_config_error = running & i_valid & !configuration_ok;
        wire input_permitted = running & !o_config_error;
        wire [RESULT_WIDTH-1:0] result = {
            translated_data[2*DATA_BITS-1:0], translated_strobe[2*WORD_BYTES-1:0],
            translated_data[3*DATA_BITS-1:2*DATA_BITS], translated_strobe[3*WORD_BYTES-1:2*WORD_BYTES],
            i_shift_high, (|input_strobe) & (|i_offset),
            (|translated_strobe[WORD_BYTES-1:0]) & (|translated_strobe[2*WORD_BYTES-1:WORD_BYTES]),
            i_last, i_user
        };
        wire [RESULT_WIDTH-1:0] selected_result;
        wire [RESULT_WIDTH-1:0] visible_result;

        if (REGISTER_OUTPUTS == 1) begin : g_registered
            wire stored_valid;
            wire [RESULT_WIDTH-1:0] stored_result;
            wire room = !stored_valid | i_ready;
            wire accept = input_permitted & i_valid & room;
            dff #(.WIDTH(RESULT_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_result (
                .i_clk(i_clk), .i_rstb(i_rstb), .i_enable(accept),
                .i_d(result), .o_q(stored_result)
            );
            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
                .i_clk(i_clk), .i_rstb(i_rstb),
                .i_enable(i_flush | (running & room)),
                .i_d(!i_flush & i_valid & !o_config_error), .o_q(stored_valid)
            );
            assign o_ready = input_permitted & room;
            assign o_valid = running & stored_valid;
            assign o_busy = stored_valid;
            assign selected_result = stored_result;
        end else begin : g_combinational
            wire unused_clock = i_clk;
            assign o_ready = input_permitted & i_ready;
            assign o_valid = input_permitted & i_valid;
            assign o_busy = 1'b0;
            assign selected_result = result;
        end

        operand_isolation #(.WIDTH(RESULT_WIDTH)) u_output_clamp (
            .i_data(selected_result),
            .i_isolate(!o_valid),
            .o_data(visible_result)
        );

        assign {o_data_hi, o_data_lo, o_strb_hi, o_strb_lo, o_spill_data, o_spill_strb,
                o_spill_high, o_unaligned, o_split, o_last, o_user} = visible_result;
    end
endmodule
