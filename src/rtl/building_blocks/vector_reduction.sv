`timescale 1ns / 1ps
`default_nettype none

// Parallel masked integer reduction, with one operation accepted per enabled
// edge. Trees are combinational; LATENCY adds a globally stalled response path.
module vector_reduction #(
    parameter ELEMENT_WIDTH = 8,
    parameter NUM_ELEMENTS = 4,
    parameter ACC_WIDTH = 32,
    parameter SUPPORT_SUM = 1,
    parameter SUPPORT_MINMAX = 1,
    parameter SUPPORT_LOGICAL = 1,
    parameter LATENCY = 1,
    parameter MAX_LATENCY = 8,
    parameter ASYNC_RESET = 0,
    parameter OPCODE_WIDTH = 3,
    parameter RESULT_FORMAT_WIDTH = 2,
    localparam bit PARAMETERS_VALID =
        ((ELEMENT_WIDTH >= 1 && ELEMENT_WIDTH <= 536870800) === 1'b1) &&
        ( ^ ELEMENT_WIDTH !== 1'bx) &&
        ((NUM_ELEMENTS >= 1 && NUM_ELEMENTS <= 536870911) === 1'b1) &&
        ( ^ NUM_ELEMENTS !== 1'bx) &&
        ((ACC_WIDTH >= 1 && ACC_WIDTH <= 2147483600) === 1'b1) &&
        ( ^ ACC_WIDTH !== 1'bx) &&
        ((128'(ACC_WIDTH) >= 128'(ELEMENT_WIDTH) + 128'($clog2(NUM_ELEMENTS))) === 1'b1) &&
        ((MAX_LATENCY >= 1 && MAX_LATENCY <= 2147483646) === 1'b1) &&
        ( ^ MAX_LATENCY !== 1'bx) &&
        ((LATENCY >= 0 && LATENCY <= MAX_LATENCY) === 1'b1) && ( ^ LATENCY !== 1'bx) &&
        ((SUPPORT_SUM === 0) || (SUPPORT_SUM === 1)) &&
        ((SUPPORT_MINMAX === 0) || (SUPPORT_MINMAX === 1)) &&
        ((SUPPORT_LOGICAL === 0) || (SUPPORT_LOGICAL === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        (OPCODE_WIDTH === 3) && (RESULT_FORMAT_WIDTH === 2) &&
        ((128'(NUM_ELEMENTS) * 128'(ELEMENT_WIDTH) < 128'd2147483647) === 1'b1) &&
        (((128'(ACC_WIDTH) + 128'(ELEMENT_WIDTH) + 128'($clog2(NUM_ELEMENTS)) + 64) *
            (128'(LATENCY) + 1) < 128'd2147483647) === 1'b1) &&
        (((128'(1) << $clog2(NUM_ELEMENTS)) *
            (128'(ELEMENT_WIDTH) + 128'($clog2(NUM_ELEMENTS)) + 1) * 16 <
            128'd2147483647) === 1'b1),
    localparam int E = PARAMETERS_VALID ? ELEMENT_WIDTH : 1,
    localparam int N = PARAMETERS_VALID ? NUM_ELEMENTS : 1,
    localparam int A = PARAMETERS_VALID ? ACC_WIDTH : 1,
    localparam int L = PARAMETERS_VALID ? LATENCY : 0,
    localparam int PACKED_WIDTH = N * E,
    localparam int SUM_GROWTH = $clog2(N),
    localparam int SUM_WIDTH = E + SUM_GROWTH,
    localparam int ACTIVE_COUNT_WIDTH = $clog2(N + 1)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [2:0] i_opcode,
    input logic [N-1:0] i_element_mask,
    input logic [PACKED_WIDTH-1:0] i_data,
    input logic i_signed,
    output wire o_valid,
    output wire [A-1:0] o_result,
    output wire [1:0] o_result_format,
    output wire o_result_signed,
    output wire [ACTIVE_COUNT_WIDTH-1:0] o_active_count,
    output wire o_zero,
    output wire o_negative,
    output wire o_illegal_operation
);
    import vector_reduction_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        vector_reduction_parameters_must_be_valid invalid_parameters ();
    end else begin : g_reduction
        localparam int C = ACTIVE_COUNT_WIDTH;
        localparam int LEAVES = 2 ** SUM_GROWTH;

        // Width-dependent response storage stays beside the parameterized ports.
        typedef struct packed {
            logic [A-1:0] result;
            vector_reduction_result_format_t format;
            logic signed_result;
            logic [C-1:0] count;
            logic zero;
            logic negative;
            logic illegal;
        } response_t;

        localparam int PAYLOAD = $bits(response_t);
        localparam int CONTROLS = PAYLOAD - A;
        wire controls_known = ( ^ {i_opcode, i_element_mask, i_signed} !== 1'bx);
        logic supported;

        always_comb begin
            supported = 1'b0;

            case (i_opcode)
                VRED_SUM: supported = SUPPORT_SUM == 1;
                VRED_MIN, VRED_MAX: supported = SUPPORT_MINMAX == 1 && (|i_element_mask);
                VRED_AND, VRED_OR: supported = SUPPORT_LOGICAL == 1;
                default: supported = 1'b0;
            endcase
        end

        wire legal = i_valid === 1'b1 && controls_known && supported;
        wire illegal = i_valid === 1'b1 && !legal;
        wire fire;

        if (L == 0) begin : g_combinational
            assign fire = legal;
        end else begin : g_registered
            assign fire = legal && i_rstb === 1'b1 && i_clock_enable === 1'b1;
        end

        if (SUPPORT_SUM == 0 && SUPPORT_MINMAX == 0 && SUPPORT_LOGICAL == 0) begin : g_no_ops
            // With no operation implemented, only legality/response controls remain.
            wire [PACKED_WIDTH-1:0] unused_data = i_data;
        end
        wire [A-1:0] results[5];

        for (genvar op = 0; op < 5; op++) begin : g_operation
            if ((op == 0 && SUPPORT_SUM == 1) ||
                ((op == 1 || op == 2) && SUPPORT_MINMAX == 1) ||
                ((op == 3 || op == 4) && SUPPORT_LOGICAL == 1)) begin : g_enabled
                localparam int W = op == 0 ? SUM_WIDTH : E;
                wire active = fire && i_opcode == 3'(op);
                wire [W-1:0] value;

                vector_reduction_tree #(.ELEMENT_WIDTH(E), .NUM_ELEMENTS(N),
                    .OPERATION(op)) u_tree (
                    .i_enable(active),
                    .i_mask(i_element_mask),
                    .i_data(i_data),
                    .i_signed(active && i_signed),
                    .o_result(value)
                );

                assign results[op] = {{(A - W){active && i_signed && value[W-1]}}, value};
            end else begin : g_disabled
                assign results[op] = '0;
            end
        end

        // The metadata count uses the same balanced shape, including padded zeros.
        for (genvar level = 0; level <= SUM_GROWTH; level++) begin : g_count
            localparam int NODES = LEAVES >> level;
            wire [C-1:0] count[NODES];

            for (genvar k = 0; k < NODES; k++) begin : g_node
                if (level == 0) begin : g_leaf
                    if (k < N) begin : g_element
                        assign count[k] = C'(fire && i_element_mask[k]);
                    end else begin : g_padding
                        assign count[k] = '0;
                    end
                end else begin : g_branch
                    assign count[k] = g_count[level-1].count[2*k] +
                        g_count[level-1].count[2*k+1];
                end
            end
        end

        response_t request;

        always_comb begin
            request = '0;
            request.illegal = illegal;

            if (fire) begin
                case (i_opcode)
                    VRED_SUM: request.result = results[0];
                    VRED_MIN: request.result = results[1];
                    VRED_MAX: request.result = results[2];
                    VRED_AND: request.result = results[3];
                    VRED_OR: request.result = results[4];
                    default: request.result = '0;
                endcase

                request.format = i_opcode == VRED_SUM ?
                    vector_lane_pkg::VLANE_RESULT_ACCUMULATOR :
                    vector_lane_pkg::VLANE_RESULT_ELEMENT;
                request.signed_result = i_signed;
                request.count = g_count[SUM_GROWTH].count[0];
                request.zero = request.result == 0;
                request.negative = i_signed && request.result[A-1];
            end
        end

        response_t response;

        vector_lane_pipeline #(.WIDTH(PAYLOAD), .CONTROL_WIDTH(CONTROLS), .DEPTH(L),
            .ASYNC_RESET(ASYNC_RESET != 0)) u_response (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_clock_enable(i_clock_enable),
            .i_valid(i_valid),
            .i_data(request),
            .o_valid(o_valid),
            .o_data(response)
        );

        wire result_valid;
        wire unused_suppressed;

        write_gate u_write (
            .i_write_enable(o_valid === 1'b1),
            .i_suppress(response.illegal),
            .o_write_enable(result_valid),
            .o_write_suppressed(unused_suppressed)
        );

        operand_isolation #(.WIDTH(PAYLOAD - 1)) u_output (
            .i_data({response.result, response.format, response.signed_result,
                response.count, response.zero, response.negative}),
            .i_isolate(!result_valid),
            .o_data({o_result, o_result_format, o_result_signed,
                o_active_count, o_zero, o_negative})
        );
        assign o_illegal_operation = o_valid && response.illegal;

`ifdef MOSAIC_VECTOR_REDUCTION_ASSERTIONS
        vector_reduction_assertions #(
            .E(E),
            .N(N),
            .A(A),
            .L(L),
            .ASYNC_RESET(ASYNC_RESET),
            .SUM(SUPPORT_SUM),
            .MINMAX(SUPPORT_MINMAX),
            .LOGICAL(SUPPORT_LOGICAL)) u_assertions (.*);
`endif
    end
endmodule
`default_nettype wire
