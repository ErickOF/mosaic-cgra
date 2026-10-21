`timescale 1ns / 1ps

// One descriptor at a time, one byte address per accepted clock. A shared,
// handshake-isolated extended adder serves inner steps and row-base steps.
module agu #(
    parameter ADDR_WIDTH = 32,
    parameter COUNT_WIDTH = 16,
    parameter MAX_ELEMENT_BYTES = 16,
    parameter SPACE_ID_WIDTH = 2,
    parameter CHANNEL_ID_WIDTH = 4,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter ASYNC_RESET = 0,
    parameter MODE_WIDTH = 2,
    localparam bit PARAMETERS_VALID =
        ((ADDR_WIDTH >= 1) === 1'b1) && (^ADDR_WIDTH !== 1'bx) &&
        ((COUNT_WIDTH >= 1) === 1'b1) && (^COUNT_WIDTH !== 1'bx) &&
        ((MAX_ELEMENT_BYTES >= 1) === 1'b1) && (^MAX_ELEMENT_BYTES !== 1'bx) &&
        (((MAX_ELEMENT_BYTES & (MAX_ELEMENT_BYTES-1)) == 0) === 1'b1) &&
        ((ADDR_WIDTH >= $clog2(MAX_ELEMENT_BYTES)) === 1'b1) &&
        ((SPACE_ID_WIDTH >= 1) === 1'b1) && (^SPACE_ID_WIDTH !== 1'bx) &&
        ((CHANNEL_ID_WIDTH >= 1) === 1'b1) && (^CHANNEL_ID_WIDTH !== 1'bx) &&
        ((CONTEXT_ID_WIDTH >= 1) === 1'b1) && (^CONTEXT_ID_WIDTH !== 1'bx) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) && (MODE_WIDTH === 2),
    localparam int W = PARAMETERS_VALID ? ADDR_WIDTH : 1,
    localparam int C = PARAMETERS_VALID ? COUNT_WIDTH : 1,
    localparam int S = PARAMETERS_VALID ? SPACE_ID_WIDTH : 1,
    localparam int H = PARAMETERS_VALID ? CHANNEL_ID_WIDTH : 1,
    localparam int T = PARAMETERS_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int MAX_ELEMENT_LOG2 = PARAMETERS_VALID ? $clog2(MAX_ELEMENT_BYTES) : 0,
    localparam int ELEMENT_SIZE_WIDTH = (MAX_ELEMENT_LOG2 < 1) ? 1 : $clog2(MAX_ELEMENT_LOG2+1),
    localparam int ACCEPTED_COUNT_WIDTH = 2*C
) (
    input logic i_clk, i_rstb, i_error_clear,
    input logic i_config_valid,
    output logic o_config_ready,
    input logic [1:0] i_mode,
    input logic [W-1:0] i_base_address,
    input logic [C-1:0] i_inner_count, i_outer_count,
    input logic [W-1:0] i_inner_stride, i_outer_stride,
    input logic [ELEMENT_SIZE_WIDTH-1:0] i_element_size_log2,
    input logic i_is_write,
    input logic [S-1:0] i_address_space,
    input logic [H-1:0] i_channel_id,
    input logic [T-1:0] i_context_id,
    input logic i_emit_end_of_stream,
    output logic o_valid,
    input logic i_ready,
    output logic [W-1:0] o_address,
    output logic [C-1:0] o_inner_index, o_outer_index,
    output logic o_first, o_last, o_row_first, o_row_last, o_end_of_stream,
    output logic [ELEMENT_SIZE_WIDTH-1:0] o_element_size_log2,
    output logic o_is_write,
    output logic [S-1:0] o_address_space,
    output logic [H-1:0] o_channel_id,
    output logic [T-1:0] o_context_id,
    output logic o_idle, o_active,
    output logic o_descriptor_started, o_address_accepted, o_completed,
    output logic [ACCEPTED_COUNT_WIDTH-1:0] o_addresses_accepted,
    output logic o_error,
    output logic [agu_pkg::ERROR_CODE_WIDTH-1:0] o_error_code
);
    import agu_pkg::*;
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        agu_parameters_must_be_valid invalid_parameters ();
    end else begin : g_sequence
        localparam int META_BITS = ELEMENT_SIZE_WIDTH+S+H+T+2;
        localparam int DESC_BITS = 2*C+2*(W+2)+2+META_BITS;
        logic active;
        logic [C-1:0] inner_index, outer_index, inner_last, outer_last;
        logic [W-1:0] address, row_base;
        logic [1:0] mode;
        logic [META_BITS-1:0] metadata;
        logic signed [W+1:0] inner_delta, outer_delta, configured_inner;
        logic signed [W+1:0] add_left, add_right;
        wire signed [W+1:0] candidate = add_left + add_right;
        logic [W-1:0] alignment_mask;
        agu_error_t descriptor_error;
        wire config_accept = o_config_ready && (i_config_valid === 1'b1);
        wire address_accept = active && (i_ready === 1'b1) && (i_rstb === 1'b1);
        wire row_last = inner_index == inner_last;
        wire last = row_last && (outer_index == outer_last);
        wire row_step = row_last && (mode == AGU_STRIDED_2D);
        wire calculate = address_accept && !last;
        // Two extension bits accommodate both an unsigned address and +2**W
        // linear steps, including the smallest legal address/element geometry.
        wire below_range = candidate[W+1];
        wire above_range = !candidate[W+1] && candidate[W];
        wire range_error = calculate && (below_range || above_range);
        wire advance = calculate && !range_error;
        wire clear_error = !active && (i_error_clear === 1'b1);
        wire start = config_accept && (descriptor_error == AGU_ERR_NONE);
        wire bad_descriptor = config_accept && (descriptor_error != AGU_ERR_NONE);
        wire finish = address_accept && last;
        wire [8:0] unused_counter_status;
        wire unused_emit;
        wire [ERROR_CODE_WIDTH-1:0] next_error = clear_error ? AGU_ERR_NONE
            : bad_descriptor ? descriptor_error : below_range ? AGU_ERR_UNDERFLOW : AGU_ERR_OVERFLOW;
        wire unsupported_size;
        if (MAX_ELEMENT_LOG2 == (2**ELEMENT_SIZE_WIDTH)-1) begin : g_all_sizes
            assign unsupported_size = 1'b0;
        end else begin : g_size_limit
            assign unsupported_size = i_element_size_log2 > ELEMENT_SIZE_WIDTH'(MAX_ELEMENT_LOG2);
        end
        wire [META_BITS-1:0] input_metadata = {i_element_size_log2, i_is_write,
            i_address_space, i_channel_id, i_context_id, i_emit_end_of_stream};
        wire [DESC_BITS-1:0] descriptor = {i_inner_count-{{(C-1){1'b0}},1'b1},
            i_outer_count-{{(C-1){1'b0}},1'b1}, configured_inner,
            {{2{i_outer_stride[W-1]}},i_outer_stride}, i_mode, input_metadata};

        assign o_config_ready = !active && !o_error && (i_rstb === 1'b1)
            && (i_error_clear === 1'b0);
        assign o_valid = active;
        assign o_active = active;
        assign o_error = o_error_code != AGU_ERR_NONE;
        assign o_idle = !active && !o_error;

        // Check knownness before numeric comparisons. Ignored strides are never
        // included in the required-field reduction. Mode has first priority;
        // unknown required fields precede the remaining listed error classes.
        always_comb begin
            descriptor_error = AGU_ERR_NONE;
            alignment_mask = '0;
            configured_inner = '0;
            if (config_accept) begin
                case (i_mode)
                    AGU_LINEAR_1D, AGU_STRIDED_1D, AGU_STRIDED_2D: begin
                        if ((^{i_base_address,i_inner_count,i_outer_count,i_element_size_log2,
                            input_metadata} === 1'bx) ||
                            ((i_mode != AGU_LINEAR_1D) && (^i_inner_stride === 1'bx)) ||
                            ((i_mode == AGU_STRIDED_2D) && (^i_outer_stride === 1'bx)))
                            descriptor_error = AGU_ERR_UNKNOWN_FIELD;
                        else if (i_inner_count == '0) descriptor_error = AGU_ERR_INNER_COUNT;
                        else if (i_outer_count == '0) descriptor_error = AGU_ERR_OUTER_COUNT;
                        else if ((i_mode != AGU_STRIDED_2D) && (i_outer_count != C'(1)))
                            descriptor_error = AGU_ERR_1D_OUTER_COUNT;
                        else if (unsupported_size)
                            descriptor_error = AGU_ERR_ELEMENT_SIZE;
                        else begin
                            alignment_mask = W'(({{(W+1){1'b0}},1'b1} << i_element_size_log2)-1'b1);
                            configured_inner = (i_mode == AGU_LINEAR_1D)
                                ? ({{(W+1){1'b0}},1'b1} << i_element_size_log2)
                                : $signed({{2{i_inner_stride[W-1]}},i_inner_stride});
                            if (|(i_base_address & alignment_mask)) descriptor_error = AGU_ERR_BASE_ALIGNMENT;
                            else if ((i_mode != AGU_LINEAR_1D) && (|(i_inner_stride & alignment_mask)))
                                descriptor_error = AGU_ERR_INNER_ALIGNMENT;
                            else if ((i_mode == AGU_STRIDED_2D) && (|(i_outer_stride & alignment_mask)))
                                descriptor_error = AGU_ERR_OUTER_ALIGNMENT;
                        end
                    end
                    default: descriptor_error = AGU_ERR_MODE;
                endcase
            end
        end

        // Only accepted nonfinal addresses activate the shared recurrence cone.
        // Stalls, idle, sticky error and final completion clamp both operands.
        operand_isolation #(.WIDTH(W+2)) u_add_left (
            .i_data({2'b00, row_step ? row_base : address}),
            .i_isolate(!calculate),
            .o_data(add_left));

        operand_isolation #(.WIDTH(W+2)) u_add_right (
            .i_data(row_step ? outer_delta : inner_delta),
            .i_isolate(!calculate),
            .o_data(add_right));

        // Unreset descriptor and address storage is visible only while active.
        // Row state changes only on configuration or a successful 2D row step.
        dff #(.WIDTH(DESC_BITS)) u_descriptor (
            .i_clk(i_clk),
            .i_rstb(1'b1),
            .i_enable(start),
            .i_d(descriptor),
            .o_q({inner_last, outer_last, inner_delta, outer_delta, mode, metadata}));

        dff #(.WIDTH(W)) u_address (
            .i_clk(i_clk),
            .i_rstb(1'b1),
            .i_enable(start || advance),
            .i_d(start ? i_base_address : candidate[W-1:0]),
            .o_q(address));

        dff #(.WIDTH(W)) u_row_base (
            .i_clk(i_clk),
            .i_rstb(1'b1),
            .i_enable(start || (advance && row_step)),
            .i_d(start ? i_base_address : candidate[W-1:0]),
            .o_q(row_base));

        // Shared counters have explicit enables and never count a rejected or
        // stalled address. A range-failing current address still counts once.
        counter #(.WIDTH(C), .ASYNC_RESET(ASYNC_RESET != 0), .SATURATE(1'b0)) u_inner (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(advance && !row_step),
            .i_clear(start || (advance && row_step)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({C{1'b0}}),
            .o_count(inner_index),
            .o_overflow(unused_counter_status[0]),
            .o_underflow(unused_counter_status[1]),
            .o_terminal(unused_counter_status[2]));

        counter #(.WIDTH(C), .ASYNC_RESET(ASYNC_RESET != 0), .SATURATE(1'b0)) u_outer (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(advance && row_step),
            .i_clear(start),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({C{1'b0}}),
            .o_count(outer_index),
            .o_overflow(unused_counter_status[3]),
            .o_underflow(unused_counter_status[4]),
            .o_terminal(unused_counter_status[5]));

        counter #(.WIDTH(ACCEPTED_COUNT_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0), .SATURATE(1'b0)) u_accepted (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(address_accept),
            .i_clear(config_accept || clear_error),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({ACCEPTED_COUNT_WIDTH{1'b0}}),
            .o_count(o_addresses_accepted),
            .o_overflow(unused_counter_status[6]),
            .o_underflow(unused_counter_status[7]),
            .o_terminal(unused_counter_status[8]));

        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_active (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(start || finish || range_error),
            .i_d(start),
            .o_q(active));

        dff #(.WIDTH(ERROR_CODE_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_error (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(clear_error || bad_descriptor || range_error),
            .i_d(next_error),
            .o_q(o_error_code));

        dff #(.WIDTH(3), .ASYNC_RESET(ASYNC_RESET != 0)) u_pulses (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(start || address_accept || o_descriptor_started || o_address_accepted || o_completed),
            .i_d({start,address_accept,finish}),
            .o_q({o_descriptor_started,o_address_accepted,o_completed}));

        operand_isolation #(.WIDTH(W+2*C+META_BITS)) u_output (
            .i_data({address,inner_index,outer_index,metadata}),
            .i_isolate(!active),
            .o_data({o_address, o_inner_index,o_outer_index, o_element_size_log2, o_is_write,
                o_address_space, o_channel_id, o_context_id, unused_emit}));

        assign o_row_first = active && (inner_index == '0);
        assign o_row_last = active && row_last;
        assign o_first = o_row_first && (outer_index == '0);
        assign o_last = active && last;
        assign o_end_of_stream = o_last && metadata[0];

`ifdef MOSAIC_AGU_ASSERTIONS
        agu_assertions #(.W(W),.C(C),.E(ELEMENT_SIZE_WIDTH),.S(S),.H(H),.T(T),
            .ASYNC_RESET(ASYNC_RESET)) u_assertions (.*);
`endif
    end
endmodule
