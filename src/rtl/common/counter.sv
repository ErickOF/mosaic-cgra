`timescale 1ns / 1ps

// Parameterizable up/down counter with load, clear, boundary events, and
// statically selected saturating or wrapping arithmetic.
module counter #(
    parameter int unsigned             WIDTH       = 32,
    parameter logic        [WIDTH-1:0] RESET_VALUE = '0,
    parameter bit                      ASYNC_RESET = 1'b0,
    parameter bit                      SATURATE    = 1'b1
) (
    input  logic             i_clk,
    input  logic             i_rstb,
    input  logic             i_enable,
    input  logic             i_clear,
    input  logic             i_load,
    input  logic             i_direction,
    input  logic [WIDTH-1:0] i_load_value,
    output logic [WIDTH-1:0] o_count,
    output logic             o_overflow,
    output logic             o_underflow,
    output logic             o_terminal
);
    localparam logic [WIDTH-1:0] MaxValue = {WIDTH{1'b1}};

    if (WIDTH == 0) begin : gen_invalid_width
        initial $fatal(1, "WIDTH must be greater than zero");
    end

    // A direction-aware boundary indication remains independent of enable.
    always_comb begin
        o_terminal = 1'b0;
        case (i_direction)
            1'b0: o_terminal = (o_count == MaxValue);
            1'b1: o_terminal = (o_count == '0);
            default: o_terminal = 1'b0;
        endcase
    end

    // Keep reset structure explicit while sharing the clocked command behavior.
    if (ASYNC_RESET) begin : gen_async_reset
        always_ff @(posedge i_clk or negedge i_rstb) begin
            if (!i_rstb) begin
                o_count     <= RESET_VALUE;
                o_overflow  <= 1'b0;
                o_underflow <= 1'b0;
            end else begin
                o_overflow  <= 1'b0;
                o_underflow <= 1'b0;
                if (i_clear) begin
                    o_count <= RESET_VALUE;
                end else if (i_load) begin
                    o_count <= i_load_value;
                end else if (i_enable) begin
                    if (!i_direction) begin
                        if (o_count == MaxValue) begin
                            o_overflow <= 1'b1;
                            if (!SATURATE) o_count <= '0;
                        end else begin
                            o_count <= o_count + 1'b1;
                        end
                    end else begin
                        if (o_count == '0) begin
                            o_underflow <= 1'b1;
                            if (!SATURATE) o_count <= MaxValue;
                        end else begin
                            o_count <= o_count - 1'b1;
                        end
                    end
                end
            end
        end
    end else begin : gen_sync_reset
        always_ff @(posedge i_clk) begin
            if (!i_rstb) begin
                o_count     <= RESET_VALUE;
                o_overflow  <= 1'b0;
                o_underflow <= 1'b0;
            end else begin
                o_overflow  <= 1'b0;
                o_underflow <= 1'b0;
                if (i_clear) begin
                    o_count <= RESET_VALUE;
                end else if (i_load) begin
                    o_count <= i_load_value;
                end else if (i_enable) begin
                    if (!i_direction) begin
                        if (o_count == MaxValue) begin
                            o_overflow <= 1'b1;
                            if (!SATURATE) o_count <= '0;
                        end else begin
                            o_count <= o_count + 1'b1;
                        end
                    end else begin
                        if (o_count == '0) begin
                            o_underflow <= 1'b1;
                            if (!SATURATE) o_count <= MaxValue;
                        end else begin
                            o_count <= o_count - 1'b1;
                        end
                    end
                end
            end
        end
    end
endmodule
