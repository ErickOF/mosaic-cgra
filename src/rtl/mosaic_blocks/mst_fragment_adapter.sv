`timescale 1ns / 1ps
`default_nettype none
// Translate ordered logical elements into canonical local-memory fragments.
// Requests preserve element order; responses may return in any tag order. Reset
// requires endpoint epoch recovery; cancellation drains every accepted fragment.
module mst_fragment_adapter #(
    parameter int ADDR_WIDTH = 32,
    parameter int ELEMENT_DATA_WIDTH = 128,
    parameter int MEMORY_DATA_WIDTH = 64,
    parameter int MAX_OUTSTANDING = 8,
    parameter int SLOT_WIDTH = 3,
    parameter int GENERATION_WIDTH = 64,
    parameter int BYTE_COUNT_WIDTH = 38,
    parameter int EPOCH_WIDTH = 8,
    parameter int IDENTITY_WIDTH = 128,
    parameter int WRITE = 0,
    parameter int PROTECTION = 0,
    parameter int ASYNC_RESET = 0,
    localparam int A = ADDR_WIDTH,
    localparam int D = ELEMENT_DATA_WIDTH,
    localparam int MD = MEMORY_DATA_WIDTH,
    localparam int Y = D / 8,
    localparam int MY = MD / 8,
    localparam int N = MAX_OUTSTANDING,
    localparam int SI = SLOT_WIDTH,
    localparam int SG = GENERATION_WIDTH,
    localparam int EP = EPOCH_WIDTH,
    localparam int ID = IDENTITY_WIDTH,
    localparam int SZ = $clog2($clog2(Y) + 1) > 0 ? $clog2($clog2(Y) + 1) : 1,
    localparam int MSZ = MY > 1 ? $clog2($clog2(MY) + 1) : 1,
    localparam int F = Y + 1,
    localparam int FI = $clog2(F),
    localparam int MT = SG + EP + SI + FI,
    localparam int OC = $clog2(N + 1),
    localparam int BC = BYTE_COUNT_WIDTH
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_clear,
    input wire i_cancel,
    input wire i_issue_enable,
    input wire [EP-1:0] i_epoch,
    input wire [ID-1:0] i_identity,
    input wire i_logical_valid,
    output wire o_logical_ready,
    input wire [A-1:0] i_logical_address,
    input wire [SZ-1:0] i_logical_size,
    input wire [SI-1:0] i_logical_tag,
    input wire [D-1:0] i_logical_data,
    output wire o_logical_response_valid,
    input wire i_logical_response_ready,
    output wire [SI-1:0] o_logical_response_tag,
    output wire [D-1:0] o_logical_response_data,
    output wire o_logical_response_error,
    output wire o_memory_valid,
    input wire i_memory_ready,
    output wire [A-1:0] o_memory_address,
    output wire [MSZ-1:0] o_memory_size,
    output wire [MD-1:0] o_memory_data,
    output wire [MY-1:0] o_memory_strobe,
    output wire [MT-1:0] o_memory_tag,
    input wire i_response_valid,
    output wire o_response_ready,
    input wire [MT-1:0] i_response_tag,
    input wire [ID-1:0] i_response_identity,
    input wire [MD-1:0] i_response_data,
    input wire i_response_error,
    input wire [$clog2(MY+1)-1:0] i_response_committed,
    output wire [OC-1:0] o_outstanding,
    output wire [BC-1:0] o_bytes,
    output wire o_progress,
    output wire o_idle,
    output wire o_error,
    output wire [7:0] o_error_code
);
    import mst_pkg::*;

    typedef struct packed {
        logic allocated;
        logic error;
        logic [SG-1:0] generation;
        logic [A-1:0] address;
        logic [SZ-1:0] size;
        logic [2*D-1:0] window_data;
        logic [F-1:0] issued;
        logic [F-1:0] returned;
    } entry_t;

    typedef struct packed {
        logic [SI-1:0] issue_slot;
        logic offer;
        logic [SI-1:0] offer_slot;
        logic [FI-1:0] offer_fragment;
        logic [OC-1:0] outstanding;
        logic [BC-1:0] bytes;
        logic [7:0] error;
    } control_t;

    typedef struct packed {
        logic [A-1:0] address;
        logic [MSZ-1:0] size;
        logic [FI:0] count;
        logic [Y:0] useful;
    } plan_t;

    localparam int ENTRY = $bits(entry_t);
    wire [ENTRY-1:0] entries [N];
    logic [ENTRY-1:0] next_entries [N];
    wire [N-1:0] bad;
    wire control_bad;
    control_t q;
    control_t n;
    entry_t offered;
    entry_t completed;
    plan_t offer_plan;
    logic any_entry;
    logic [N-1:0] complete_candidates;
    wire complete_valid;
    wire [SI-1:0] complete_slot;
    wire arbiter_error;
    wire run = i_rstb === 1'b1;
    wire integrity_bad = (|bad) || control_bad || arbiter_error;
    wire take_logical = i_logical_valid === 1'b1 && o_logical_ready;
    wire take_request = o_memory_valid && i_memory_ready === 1'b1;
    wire take_response = i_response_valid === 1'b1 && o_response_ready;
    wire take_result = o_logical_response_valid && i_logical_response_ready === 1'b1;
    wire [2*D-1:0] write_window;
    wire [D-1:0] aligned_read;
    wire [Y-1:0] read_mask;
    wire [Y-1:0] logical_mask = Y'(({{Y{1'b0}}, 1'b1} <<
        (128'd1 << i_logical_size)) - 1'b1);

    function automatic plan_t plan(input entry_t x, input int fragment);
        plan_t p;
        logic [A:0] address;
        logic [Y:0] remaining;
        logic [Y:0] size;
        logic [Y:0] length;
        int index;
        p = '0;
        size = (Y + 1)'(128'd1 << x.size);

        if (WRITE == 0) begin
            p.count = (FI + 1)'((int'(x.address % MY) + int'(size) + MY - 1) / MY);
            p.address = A'(128'(x.address) / MY * MY + 128'(fragment * MY));
            p.size = MSZ'($clog2(MY));

            for (int b = 0; b < MY; b++)
                if (128'(p.address) + 128'(b) >= 128'(x.address) &&
                    128'(p.address) + 128'(b) < 128'(x.address) + 128'(size))
                    p.useful = p.useful + 1'b1;
        end else begin
            address = {1'b0, x.address};
            remaining = size;
            index = 0;

            for (int f = 0; f < F; f++) begin
                length = 1;

                if (remaining != 0) begin
                    for (int exponent = 0; exponent <= $clog2(MY); exponent++) begin
                        if ((128'd1 << exponent) <= 128'(remaining) &&
                            128'(address) % (128'd1 << exponent) == 0)
                            length = (Y + 1)'(128'd1 << exponent);
                    end

                    if (index == fragment) begin
                        p.address = address[A-1:0];
                        p.useful = length;

                        for (int exponent = 0; exponent <= $clog2(MY); exponent++)
                            if (length == (Y + 1)'(128'd1 << exponent)) p.size = MSZ'(exponent);
                    end

                    address = address + (A + 1)'(length);
                    remaining = remaining - length;
                    index++;
                end
            end

            p.count = (FI + 1)'(index);
        end

        return p;
    endfunction

    data_aligner #(.DATA_WIDTH(D), .USER_WIDTH(1), .ASYNC_RESET(ASYNC_RESET)) u_write_aligner (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(1'b0),
        .i_valid(take_logical && WRITE == 1),
        .o_ready(),
        .i_data_lo(i_logical_data),
        .i_strb_lo(logical_mask),
        .i_data_hi({D{1'b0}}),
        .i_strb_hi({Y{1'b0}}),
        .i_offset(($clog2(Y) > 0 ? $clog2(Y) : 1)'(i_logical_address % Y)),
        .i_shift_high(1'b1),
        .i_last(1'b1),
        .i_user(1'b0),
        .o_valid(),
        .i_ready(1'b1),
        .o_data_lo(write_window[D-1:0]),
        .o_strb_lo(),
        .o_data_hi(write_window[D+:D]),
        .o_strb_hi(),
        .o_spill_data(),
        .o_spill_strb(),
        .o_spill_high(),
        .o_unaligned(),
        .o_split(),
        .o_last(),
        .o_user(),
        .o_config_error(),
        .o_busy()
    );

    logic [Y-1:0] requested_mask;

    always @* begin
        requested_mask = '0;

        for (int b = 0; b < Y; b++)
            if (b < (128'd1 << completed.size)) requested_mask[b] = 1'b1;
    end

    data_aligner #(.DATA_WIDTH(D), .USER_WIDTH(1), .ASYNC_RESET(ASYNC_RESET)) u_read_aligner (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(1'b0),
        .i_valid(o_logical_response_valid && WRITE == 0 &&!completed.error),
        .o_ready(),
        .i_data_lo(completed.window_data[D-1:0]),
        .i_strb_lo(Y'(({Y{1'b0}} | {{Y{1'b0}}, requested_mask}) << (completed.address % Y))),
        .i_data_hi(completed.window_data[D+:D]),
        .i_strb_hi(Y'((2 * Y)'(requested_mask) << (completed.address % Y) >> Y)),
        .i_offset(($clog2(Y) > 0 ? $clog2(Y) : 1)'(completed.address % Y)),
        .i_shift_high(1'b0),
        .i_last(1'b1),
        .i_user(1'b0),
        .o_valid(),
        .i_ready(1'b1),
        .o_data_lo(aligned_read),
        .o_strb_lo(read_mask),
        .o_data_hi(),
        .o_strb_hi(),
        .o_spill_data(),
        .o_spill_strb(),
        .o_spill_high(),
        .o_unaligned(),
        .o_split(),
        .o_last(),
        .o_user(),
        .o_config_error(),
        .o_busy()
    );

    always @* begin
        offered = '0;

        if (int'(q.offer_slot) < N) offered = entries[q.offer_slot];
        offer_plan = plan(offered, int'(q.offer_fragment));
    end

    always @* begin
        completed = '0;

        if (int'(complete_slot) < N) completed = entries[complete_slot];
    end

    always @* begin
        any_entry = 1'b0;
        complete_candidates = '0;

        for (int s = 0; s < N; s++) begin
            entry_t x;
            plan_t p;
            logic [F-1:0] mask;
            x = entries[s];
            p = plan(x, 0);
            mask = F'(({{F{1'b0}}, 1'b1} << p.count) - 1'b1);
            any_entry |= x.allocated;
            complete_candidates[s] = x.allocated &&
                ((x.returned == mask && x.issued == mask) ||
                    (i_cancel === 1'b1 && (x.issued & ~x.returned) == 0 &&
!(q.offer && q.offer_slot == SI'(s))));
        end
    end

    assign o_logical_ready = run && i_issue_enable === 1'b1 && i_cancel === 1'b0 &&
!o_error && int'(i_logical_tag) < N &&
        (entries[i_logical_tag] >> (ENTRY - 1)) == 0;
    assign o_memory_valid = run && q.offer &&!integrity_bad;
    assign o_memory_address = o_memory_valid ? offer_plan.address : {A{1'b0}};
    assign o_memory_size = o_memory_valid ? offer_plan.size : {MSZ{1'b0}};
    assign o_memory_tag = {i_epoch, offered.generation, q.offer_slot, q.offer_fragment};
    assign o_memory_strobe = WRITE == 1 && o_memory_valid ?
        MY'(((128'd1 << offer_plan.useful) - 1'b1) << (offer_plan.address % MY)) : {MY{1'b0}};
    assign o_memory_data = WRITE == 1 && o_memory_valid ?
        MD'(offered.window_data >> (8 * (128'(offer_plan.address) -
            128'(offered.address) / Y * Y))) &
            MD'(({{MD{1'b0}}, 1'b1} << (8 * offer_plan.useful)) - 1'b1) : {MD{1'b0}};
    assign o_response_ready = run;
    assign o_logical_response_valid = run && complete_valid &&!integrity_bad;
    assign o_logical_response_tag = complete_slot;
    assign o_logical_response_data = completed.error || WRITE == 1 ? {D{1'b0}} : aligned_read;
    assign o_logical_response_error = completed.error || i_cancel === 1'b1;
    assign o_outstanding = q.outstanding;
    assign o_bytes = q.bytes;
    assign o_idle =!any_entry &&!q.offer && q.outstanding == 0;
    assign o_progress = take_logical || take_request || take_response || take_result;
    assign o_error = integrity_bad || q.error != 0;
    assign o_error_code = integrity_bad ? MST_ERR_INTEGRITY : q.error;

    round_robin_arbiter #(.NUM_REQUESTERS(N), .ASYNC_RESET(ASYNC_RESET)) u_result_arbiter (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_request(complete_candidates),
        .i_eligible({N{1'b1}}),
        .i_lock({N{1'b0}}),
        .i_accept(take_result),
        .i_flush(i_clear),
        .o_grant_valid(complete_valid),
        .o_grant_onehot(),
        .o_grant_index(complete_slot),
        .o_grant_lock(),
        .o_grant_accepted(),
        .o_contended(),
        .o_pending(),
        .o_locked(),
        .o_lock_owner(),
        .o_protocol_error(arbiter_error)
    );

    always @* begin
        n = q;

        for (int s = 0; s < N; s++) next_entries[s] = entries[s];

        if (run && take_request) begin
            entry_t x;
            logic [F-1:0] issued;
            x = entries[q.offer_slot];
            issued = x.issued | (F'(1) << q.offer_fragment);
            x.issued = issued;
            next_entries[q.offer_slot] = x;
            n.offer = 1'b0;
            n.outstanding = n.outstanding + 1'b1;

            if (int'(q.offer_fragment) + 1 == int'(offer_plan.count))
                n.issue_slot = q.issue_slot == SI'(N - 1) ? {SI{1'b0}} : q.issue_slot + 1'b1;
        end

        if (run &&!q.offer && i_issue_enable === 1'b1 &&
            i_cancel === 1'b0 &&!o_error && q.outstanding < N) begin
            entry_t x;
            plan_t p;
            logic chosen;
            x = entries[q.issue_slot];
            p = plan(x, 0);
            chosen = 1'b0;

            for (int f = 0; f < F; f++) begin
                if (x.allocated && f < int'(p.count) &&!chosen &&
                    ((x.issued >> f) & 1'b1) == 0) begin
                    n.offer = 1'b1;
                    n.offer_slot = q.issue_slot;
                    n.offer_fragment = FI'(f);
                    chosen = 1'b1;
                end
            end
        end

        if (run && take_response) begin
            int s;
            int f;
            entry_t x;
            plan_t p;
            logic [2*D-1:0] window_data;
            logic [Y:0] useful;
            logic active_unknown;
            s = int'(i_response_tag[FI+:SI]);
            f = int'(i_response_tag[0+:FI]);
            x = '0;

            if (s < N) x = next_entries[s];

            p = plan(x, f);
            useful = '0;
            window_data = x.window_data;
            active_unknown = 1'b0;

            if ((^{i_response_tag, i_response_identity, i_response_error} === 1'bx) ||
                s >= N || f >= int'(p.count) ||!x.allocated ||
                i_response_tag[FI+SI+:SG] != x.generation ||
                i_response_tag[FI+SI+SG+:EP] != i_epoch || i_response_identity != i_identity ||
                ((x.issued >> f) & 1'b1) == 0 || ((x.returned >> f) & 1'b1) != 0)
                n.error = MST_ERR_TAG;
            else begin
                x.returned = x.returned | (F'(1) << f);

                if (WRITE == 1) begin
                    if (^i_response_committed === 1'bx ||
                        int'(i_response_committed) > int'(p.useful) ||
                        (!i_response_error && int'(i_response_committed) != int'(p.useful)))
                        n.error = MST_ERR_TAG;
                    else n.bytes = n.bytes + BC'(i_response_committed);
                end else if (!i_response_error) begin
                    for (int b = 0; b < MY; b++) begin
                        if (128'(p.address) + 128'(b) >= 128'(x.address) &&
                            128'(p.address) + 128'(b) < 128'(x.address) + (128'd1 << x.size)) begin

                            if (^i_response_data[b*8+:8] === 1'bx) active_unknown = 1'b1;
                            else begin
                                int byte_offset;
                                byte_offset = int'(128'(p.address) - 128'(x.address) / Y * Y);
                                window_data[(byte_offset+b)*8+:8] = i_response_data[b*8+:8];
                                useful = useful + 1'b1;
                            end
                        end
                    end

                    if (active_unknown) n.error = MST_ERR_UNKNOWN;
                    else n.bytes = n.bytes + BC'(useful);
                end

                x.window_data = window_data;
                x.error |= i_response_error || active_unknown;
                next_entries[s] = x;
                n.outstanding = n.outstanding - 1'b1;
            end
        end

        if (run && take_result) begin
            entry_t x;
            x = next_entries[complete_slot];
            x.allocated = 1'b0;
            next_entries[complete_slot] = x;
        end

        if (run && take_logical) begin
            entry_t old;
            entry_t x;
            old = entries[i_logical_tag];
            x = '0;
            x.allocated = 1'b1;
            x.generation = old.generation + 1'b1;
            x.address = i_logical_address;
            x.size = i_logical_size;
            x.window_data = WRITE == 1 ? write_window : {2 * D{1'b0}};
            next_entries[i_logical_tag] = x;

            if (&old.generation) n.error = MST_ERR_GENERATION;
        end

        if (run && i_clear === 1'b1 && o_idle) begin
            n = '0;
        end

        if (q.outstanding > N) n.error = MST_ERR_TAG;
    end

    banked_scratchpad_state #(
        .WIDTH($bits(control_t)),
        .PROTECTION(PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_control (
        .i_clk(i_clk),
        .i_reset_n(i_rstb),
        .i_data(n),
        .o_data(q),
        .o_bad(control_bad)
    );

    for (genvar s = 0; s < N; s++) begin : g_entry
        banked_scratchpad_state #(
            .WIDTH(ENTRY),
            .PROTECTION(PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_state (
            .i_clk(i_clk),
            .i_reset_n(i_rstb),
            .i_data(next_entries[s]),
            .o_data(entries[s]),
            .o_bad(bad[s])
        );
    end
endmodule
`default_nettype wire
