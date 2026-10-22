`timescale 1ns / 1ps

// Simulation safety checker; producer stability/progress are environment duties.
// Independent accepted-minus-delivered accounting checks the physical token sum.
module exp_unit_assertions #(
    parameter int CAPACITY = 7,
    parameter int COUNT_WIDTH = 3,
    parameter int RESPONSE = 67,
    parameter int RW = 40,
    parameter int RF = 20,
    parameter int EW = 20,
    parameter int I = 24
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_flush,
    input wire i_run,
    input wire i_fatal,
    input wire i_accept,
    input wire i_pop,
    input wire [COUNT_WIDTH-1:0] i_occupancy,
    input wire i_valid,
    input wire i_ready,
    input wire [RESPONSE-1:0] i_payload,
    input wire i_request_ready,
    input wire i_floor_active,
    input wire signed [RW-1:0] i_z,
    input wire signed [EW-1:0] i_k,
    input wire [RF-1:0] i_fraction,
    input wire i_interpolate,
    input wire [I-1:0] i_lower,
    input wire [I-1:0] i_upper,
    input wire [I-1:0] i_mantissa
);
    logic initialized = 1'b0;
    integer outstanding = 0;
    logic held;
    logic [RESPONSE-1:0] payload;
    logic signed [RW:0] reconstructed;

    always @(posedge i_clk) begin
        if (i_rstb === 1'b0) begin
            initialized = 1'b1;
            outstanding = 0;
            #1ps;
            assert (i_occupancy == '0 &&!i_valid &&!i_request_ready)
                else $fatal(1, "Exp reset left live state");
        end else if (initialized && i_rstb === 1'b1) begin
            if (i_flush) outstanding = 0;
            else outstanding = outstanding + int'(i_accept) - int'(i_pop);
            assert (outstanding >= 0 && outstanding <= CAPACITY)
                else $fatal(1, "Exp ownership overflow/underflow");
            if (i_floor_active) begin
                reconstructed = ((RW + 1)'(i_k) <<< RF) + $signed({1'b0, i_fraction});
                assert (reconstructed == (RW + 1)'(i_z))
                    else $fatal(1, "Exp floor reconstruction");
            end
            if (i_interpolate)
                assert (i_mantissa >= i_lower && i_mantissa <= i_upper)
                    else $fatal(1, "Exp interpolation escaped endpoints");
            held = i_valid &&!i_ready &&!i_flush &&!i_fatal;
            payload = i_payload;
            #1ps;
            assert (int'(i_occupancy) == outstanding)
                else $fatal(1, "Exp accepted/retired ownership mismatch");
            if (held && i_run &&!i_flush &&!i_fatal)
                assert (i_valid && i_payload === payload)
                    else $fatal(1, "Exp output changed under backpressure");
            if (i_fatal)
                assert (!i_request_ready &&!i_valid)
                    else $fatal(1, "Exp fatal containment");
        end
    end
endmodule
