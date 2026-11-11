`timescale 1ns / 1ps

// Asynchronously assert reset and synchronously release it into one clock domain.
module reset_synchronizer #(
    parameter int unsigned STAGES = 2
) (
    input  logic i_clk,
    input  logic i_async_rstb,
    output logic o_rstb
);
    if (STAGES < 2) begin : gen_invalid_stages
        reset_synchronizer_stages_must_be_at_least_two invalid_stages ();
    end

    // Preserve the stage chain for CDC recognition and metastability containment.
    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO", DONT_TOUCH = "TRUE" *)
    logic [STAGES-1:0] sync_stages;

    // Exclude invalid part-selects so the elaboration guard reports the cause.
    if (STAGES >= 2) begin : gen_synchronizer
        always_ff @(posedge i_clk or negedge i_async_rstb) begin
            // X/Z reset is illegal. Expose it instead of treating an unknown
            // reset as deasserted and clocking known ones through the chain.
            if (!i_async_rstb) sync_stages <= '0;
            else if (i_async_rstb !== 1'b1) sync_stages <= 'x;
            else sync_stages <= {sync_stages[STAGES-2:0], 1'b1};
        end

        assign o_rstb = sync_stages[STAGES-1];
    end
endmodule
