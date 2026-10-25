`timescale 1ns / 1ps
// Logical power hooks. A technology wrapper supplies physical switches, isolation,
// retention and the acknowledgement for each requested phase. No RTL clock mux.
module banked_scratchpad_power #(
    parameter int SUPPORT_GATING = 0,
    parameter int SUPPORT_RETENTION = 0,
    parameter int CONTROL_PROTECTION = 0,
    parameter int ASYNC_RESET = 0
) (
    input logic i_clk,
    input logic i_reset_n,
    input logic i_quiescent,
    input logic i_off_allowed,
    input logic i_publish,
    input logic i_cmd_valid,
    input logic [1:0] i_target,
    input logic i_ack,
    output wire o_cmd_ready,
    output wire [1:0] o_state,
    output wire o_clock_enable,
    output wire o_isolate,
    output wire o_save,
    output wire o_restore,
    output wire o_power_enable,
    output wire o_contents_valid,
    output wire o_busy,
    output wire o_bad
);
    import banked_scratchpad_pkg::*;

    typedef struct packed {
        logic [2:0] phase;
        logic [1:0] state;
        logic [1:0] target;
        logic destroyed;
    } power_control_t;

    power_control_t q;
    power_control_t n;
    wire bad;
    wire run = i_reset_n === 1'b1;
    wire target_known = ^i_target !== 1'bx;
    assign o_cmd_ready = run && SUPPORT_GATING == 1 && !bad &&
        q.phase == POWER_STABLE && i_quiescent && target_known &&
        (i_target != BANK_POWER_RETENTION || SUPPORT_RETENTION == 1) &&
        (i_target != BANK_POWER_OFF || i_off_allowed) &&
        (q.state == BANK_POWER_ACTIVE || i_target == BANK_POWER_ACTIVE ||
            i_target == q.state);
    assign o_state = q.state;
    assign o_busy = q.phase != POWER_STABLE;
    assign o_clock_enable = q.phase == POWER_STABLE && q.state == BANK_POWER_ACTIVE;
    assign o_isolate = q.state == BANK_POWER_RETENTION || q.state == BANK_POWER_OFF ||
        q.phase == POWER_ISOLATE || q.phase == POWER_CHANGE ||
        q.phase == POWER_WAKE || q.phase == POWER_RESTORE;
    assign o_save = q.phase == POWER_SAVE;
    assign o_restore = q.phase == POWER_RESTORE;
    assign o_power_enable = q.state < BANK_POWER_RETENTION &&
        !(q.phase == POWER_CHANGE && q.target >= BANK_POWER_RETENTION) ||
        q.phase == POWER_WAKE || q.phase == POWER_RESTORE;
    assign o_contents_valid = !q.destroyed;
    assign o_bad = bad || q.phase > POWER_RESTORE;

    always @* begin
        n = q;

        if (i_publish) n.destroyed = 1'b0;

        if (o_cmd_ready && i_cmd_valid === 1'b1 && i_target != q.state) begin
            n.target = i_target;
            n.phase = i_target == BANK_POWER_ACTIVE ? POWER_WAKE : POWER_STOP;
        end

        case (q.phase)
            POWER_STOP: begin
                n.phase = q.target == BANK_POWER_RETENTION ? POWER_SAVE :
                    q.target == BANK_POWER_CLOCK_GATED ? POWER_STABLE : POWER_ISOLATE;

                if (q.target == BANK_POWER_CLOCK_GATED) n.state = q.target;
            end
            POWER_SAVE: if (i_ack === 1'b1) n.phase = POWER_ISOLATE;
            POWER_ISOLATE: n.phase = POWER_CHANGE;
            POWER_CHANGE: if (i_ack === 1'b1) begin
                n.state = q.target;
                n.phase = POWER_STABLE;

                if (q.target == BANK_POWER_OFF) n.destroyed = 1'b1;
            end
            POWER_WAKE: if (i_ack === 1'b1) begin
                n.phase = q.state == BANK_POWER_RETENTION ? POWER_RESTORE : POWER_STABLE;

                if (q.state != BANK_POWER_RETENTION) n.state = BANK_POWER_ACTIVE;
            end
            POWER_RESTORE: if (i_ack === 1'b1) begin
                n.state = BANK_POWER_ACTIVE;
                n.phase = POWER_STABLE;
            end
            default: begin end
        endcase
    end

    banked_scratchpad_state #(
        .WIDTH($bits(power_control_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_state (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(n),
        .o_data(q),
        .o_bad(bad)
    );
endmodule
