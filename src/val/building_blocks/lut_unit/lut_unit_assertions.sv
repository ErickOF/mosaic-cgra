`timescale 1ns / 1ps

// Native simulation safety checks; numerical/order proofs live in the independent
// PyUVM ledger. Environment liveness is not assumed by these safety assertions.
module lut_unit_assertions #(
    parameter int RESULT_BITS = 1,
    parameter int PROGRAM_BITS = 1,
    parameter int PRODUCT_BITS = 1,
    parameter int LOOKUP_DEPTH = 1,
    parameter int PROGRAM_DEPTH = 1,
    parameter int LOOKUP_OCC = 1,
    parameter int PROGRAM_OCC = 1
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_flush,
    input wire i_fault,
    input wire i_fatal,
    input wire i_lookup_fire,
    input wire i_commit,
    input wire i_read,
    input wire i_predicate,
    input wire i_bank_valid,
    input wire i_interpolating,
    input wire [PRODUCT_BITS-1:0] i_product,
    input wire i_result_valid,
    input wire i_result_ready,
    input wire [RESULT_BITS-1:0] i_result,
    input wire i_program_valid,
    input wire i_program_ready,
    input wire [PROGRAM_BITS-1:0] i_program,
    input wire [LOOKUP_OCC-1:0] i_lookup_occupancy,
    input wire [PROGRAM_OCC-1:0] i_program_occupancy,
    input wire i_finish,
    input wire i_accept_event,
    input wire i_complete_event,
    input wire [11:0] i_controls
);
    logic initialized = 1'b0;
    logic result_stalled;
    logic program_stalled;
    logic [RESULT_BITS-1:0] held_result;
    logic [PROGRAM_BITS-1:0] held_program;
    integer checks = 0;

    always @(posedge i_clk) begin : check_edge
        logic accepted;
        logic completed;
        if (i_rstb !== 1'b1 || i_flush !== 1'b0 || i_fault) begin
            initialized = 1'b0;
        end else begin
            if (initialized && result_stalled)
                assert (i_result_valid && i_result === held_result)
                    else $fatal(1, "LUT result changed while stalled");
            if (initialized && program_stalled)
                assert (i_program_valid && i_program === held_program)
                    else $fatal(1, "LUT program response changed while stalled");
            assert ( ^ i_controls !== 1'bx) else $fatal(1, "Unknown LUT output control");
            assert (int'(i_lookup_occupancy) <= LOOKUP_DEPTH &&
                    int'(i_program_occupancy) <= PROGRAM_DEPTH)
                else $fatal(1, "LUT queue occupancy overflow");
            assert (!i_fatal || (!i_lookup_fire&&!i_commit))
                else $fatal(1, "LUT fatal status permitted lookup/commit");
            assert (!i_read || (i_lookup_fire && i_predicate && i_bank_valid))
                else $fatal(1, "LUT read without legal active lookup");
            assert (i_interpolating || i_product == 0)
                else $fatal(1, "Inactive LUT multiplier toggled");
            accepted = i_lookup_fire;
            completed = i_finish;
            result_stalled = i_result_valid && (i_result_ready !== 1'b1);
            program_stalled = i_program_valid && (i_program_ready !== 1'b1);
            held_result = i_result;
            held_program = i_program;
            initialized = 1'b1;
            #0.001;
            if (i_rstb === 1'b1 && i_flush === 1'b0 &&!i_fault) begin
                assert (i_accept_event == accepted && i_complete_event == completed)
                    else $fatal(1, "LUT event correspondence failed");
                checks++;
            end
        end
    end
endmodule
