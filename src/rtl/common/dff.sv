`timescale 1ns / 1ps

// Parameterized DFF bank with reset priority and optional clock-enable behavior.
// Reset style and enable support are selected statically during elaboration.
module dff #(
    parameter int unsigned WIDTH = 1,
    parameter logic [WIDTH-1:0] RESET_VALUE = '0,
    parameter bit ASYNC_RESET = 1'b0,
    parameter bit HAS_ENABLE = 1'b1
) (
    input  logic             i_clk,
    input  logic             i_rstb,
    input  logic             i_enable,
    input  logic [WIDTH-1:0] i_d,
    output logic [WIDTH-1:0] o_q
);

  // Reject an empty bank before simulation or synthesis can use it.
  if (WIDTH == 0) begin : gen_invalid_width
    initial $fatal(1, "WIDTH must be greater than zero");
  end

  // Keep each structural variant explicit so tools infer only the requested
  // reset and enable controls.
  if (ASYNC_RESET) begin : gen_async_reset
    if (HAS_ENABLE) begin : gen_enable
      always_ff @(posedge i_clk or negedge i_rstb) begin
        if (!i_rstb) begin
          o_q <= RESET_VALUE;
        end else if (i_enable) begin
          o_q <= i_d;
        end
      end
    end else begin : gen_no_enable
      always_ff @(posedge i_clk or negedge i_rstb) begin
        if (!i_rstb) begin
          o_q <= RESET_VALUE;
        end else begin
          o_q <= i_d;
        end
      end
    end
  end else begin : gen_sync_reset
    if (HAS_ENABLE) begin : gen_enable
      always_ff @(posedge i_clk) begin
        if (!i_rstb) begin
          o_q <= RESET_VALUE;
        end else if (i_enable) begin
          o_q <= i_d;
        end
      end
    end else begin : gen_no_enable
      always_ff @(posedge i_clk) begin
        if (!i_rstb) begin
          o_q <= RESET_VALUE;
        end else begin
          o_q <= i_d;
        end
      end
    end
  end
endmodule
