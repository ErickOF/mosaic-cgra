`timescale 1ns / 1ps

// Portable glitch-free clock-gating model. ASIC flows must replace or map this
// structure to one approved integrated clock-gating cell.
module clock_gate (
    input  logic i_clk,
    input  logic i_enable,
    input  logic i_test_enable,
    output logic o_gclk
);
  logic enable_latched;

  // The effective enable may change the gated-clock decision only while the
  // source clock is low, preserving complete source-clock high pulses.
  always_latch begin
    if (!i_clk) begin
      enable_latched = i_enable | i_test_enable;
    end
  end

  assign o_gclk = i_clk & enable_latched;
endmodule
