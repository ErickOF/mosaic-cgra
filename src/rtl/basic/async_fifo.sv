`timescale 1ns / 1ps
// Dual-clock FIFO. Resets are coordinated externally and released locally.
module async_fifo #(
    parameter int unsigned DATA_WIDTH = 32,
    parameter int unsigned DEPTH = 8,
    parameter int unsigned SYNC_STAGES = 2,
    parameter int unsigned ALMOST_FULL_LEVEL = DEPTH - 1,
    parameter int unsigned ALMOST_EMPTY_LEVEL = 1,
    localparam int unsigned ADDR_WIDTH = DEPTH >= 2 ? $clog2(DEPTH) : 1,
    localparam int unsigned PTR_WIDTH = ADDR_WIDTH + 1,
    localparam int unsigned LEVEL_WIDTH = DEPTH >= 2 ? $clog2(DEPTH + 1) : 2
) (
    input  logic                                         i_w_clk,
    input  logic                                         i_w_rstb,
    input  logic                                         i_w_valid,
    output logic                                         o_w_ready,
    input  logic [(DATA_WIDTH > 0 ? DATA_WIDTH : 1)-1:0] i_w_data,
    output logic                                         o_w_full,
    output logic                                         o_w_almost_full,
    output logic [                      LEVEL_WIDTH-1:0] o_w_level,
    output logic                                         o_w_init_done,
    input  logic                                         i_r_clk,
    input  logic                                         i_r_rstb,
    output logic                                         o_r_valid,
    input  logic                                         i_r_ready,
    output logic [(DATA_WIDTH > 0 ? DATA_WIDTH : 1)-1:0] o_r_data,
    output logic                                         o_r_empty,
    output logic                                         o_r_almost_empty,
    output logic [                      LEVEL_WIDTH-1:0] o_r_level,
    output logic                                         o_r_init_done
);
    // Safe declaration sizes let invalid parameters reach their explicit guard.
    localparam int unsigned STORAGE_DEPTH = DEPTH >= 2 ? DEPTH : 2;
    localparam int unsigned REGISTER_WIDTH = DATA_WIDTH > 0 ? DATA_WIDTH : 1;
    localparam int unsigned STAGES = SYNC_STAGES >= 2 ? SYNC_STAGES : 2;
    // XOR avoids a zero-width part-select at the minimum depth of two.
    localparam logic [PTR_WIDTH-1:0] FULL_MASK = PTR_WIDTH'(3) << (PTR_WIDTH - 2);

    if (DATA_WIDTH < 1 || DEPTH < 2 || (DEPTH & (DEPTH - 1)) != 0 ||
        SYNC_STAGES < 2 || ALMOST_FULL_LEVEL < 1 || ALMOST_FULL_LEVEL > DEPTH ||
        ALMOST_EMPTY_LEVEL >= DEPTH) begin : g_invalid_parameters
        // An unresolved guard rejects invalid structure during elaboration,
        // before synthesis or simulation can accept an unusable FIFO profile.
        async_fifo_parameters_must_be_valid invalid_parameters ();
    end

    logic [REGISTER_WIDTH-1:0] memory[STORAGE_DEPTH];
    logic [PTR_WIDTH-1:0] w_bin, w_gray, r_bin, r_gray;
    logic [PTR_WIDTH-1:0] w_bin_next, w_gray_next, r_bin_next, r_gray_next;
    logic w_up, r_up, w_seen_remote, r_seen_remote;
    logic w_up_next, r_up_next, w_seen_remote_next, r_seen_remote_next;
    logic w_full_next;
    logic [LEVEL_WIDTH-1:0] w_level_next, r_level_next;
    logic [REGISTER_WIDTH-1:0] r_data_next;
    logic r_data_enable;
    logic [2:0] unused_w_counter_status, unused_r_counter_status;
    logic push, pop, r_empty_next;

    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO", DONT_TOUCH = "TRUE" *)
    logic [PTR_WIDTH-1:0] r_gray_sync[STAGES];
    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO", DONT_TOUCH = "TRUE" *)
    logic [PTR_WIDTH-1:0] w_gray_sync[STAGES];
    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO", DONT_TOUCH = "TRUE" *)
    logic r_up_sync[STAGES];
    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO", DONT_TOUCH = "TRUE" *)
    logic w_up_sync[STAGES];

    function automatic logic [PTR_WIDTH-1:0] gray_to_binary(input logic [PTR_WIDTH-1:0] gray);
        logic [PTR_WIDTH-1:0] binary;
        binary[PTR_WIDTH-1] = gray[PTR_WIDTH-1];
        for (int bit_index = PTR_WIDTH - 2; bit_index >= 0; bit_index--) begin
            binary[bit_index] = binary[bit_index+1] ^ gray[bit_index];
        end
        gray_to_binary = binary;
    endfunction

    assign o_w_init_done = i_w_rstb && w_up && r_up_sync[STAGES-1];
    assign o_r_init_done = i_r_rstb && r_up && w_up_sync[STAGES-1];
    assign o_w_ready = o_w_init_done && !o_w_full;
    assign o_r_valid = o_r_init_done && !o_r_empty;
    assign push = i_w_valid && o_w_ready;
    assign pop = o_r_valid && i_r_ready;
    assign w_bin_next = w_bin + PTR_WIDTH'(push);
    assign r_bin_next = r_bin + PTR_WIDTH'(pop);
    assign w_gray_next = w_bin_next ^ (w_bin_next >> 1);
    assign r_gray_next = r_bin_next ^ (r_bin_next >> 1);
    assign r_empty_next = r_gray_next == w_gray_sync[STAGES-1];
    assign o_w_almost_full = o_w_init_done && o_w_level >= LEVEL_WIDTH'(ALMOST_FULL_LEVEL);
    assign o_r_almost_empty = !o_r_init_done || o_r_level <= LEVEL_WIDTH'(ALMOST_EMPTY_LEVEL);

    // Pointer counters wrap across address bits plus the full/empty phase bit.
    // Clear/load commands stay inactive: epoch recovery requires actual reset.
    counter #(
        .WIDTH(PTR_WIDTH),
        .RESET_VALUE({PTR_WIDTH{1'b0}}),
        .ASYNC_RESET(1'b1),
        .SATURATE(1'b0)
    ) u_w_pointer (
        .i_clk(i_w_clk),
        .i_rstb(i_w_rstb),
        .i_enable(push),
        .i_clear(1'b0),
        .i_load(1'b0),
        .i_direction(1'b0),
        .i_load_value({PTR_WIDTH{1'b0}}),
        .o_count(w_bin),
        .o_overflow(unused_w_counter_status[0]),
        .o_underflow(unused_w_counter_status[1]),
        .o_terminal(unused_w_counter_status[2])
    );

    counter #(
        .WIDTH(PTR_WIDTH),
        .RESET_VALUE({PTR_WIDTH{1'b0}}),
        .ASYNC_RESET(1'b1),
        .SATURATE(1'b0)
    ) u_r_pointer (
        .i_clk(i_r_clk),
        .i_rstb(i_r_rstb),
        .i_enable(pop),
        .i_clear(1'b0),
        .i_load(1'b0),
        .i_direction(1'b0),
        .i_load_value({PTR_WIDTH{1'b0}}),
        .o_count(r_bin),
        .o_overflow(unused_r_counter_status[0]),
        .o_underflow(unused_r_counter_status[1]),
        .o_terminal(unused_r_counter_status[2])
    );

    // Gray state captures the same next binary value used by flag lookahead.
    dff #(
        .WIDTH(PTR_WIDTH),
        .RESET_VALUE({PTR_WIDTH{1'b0}}),
        .ASYNC_RESET(1'b1),
        .HAS_ENABLE(1'b1)
    ) u_w_gray (
        .i_clk(i_w_clk),
        .i_rstb(i_w_rstb),
        .i_enable(o_w_init_done),
        .i_d(w_gray_next),
        .o_q(w_gray)
    );

    dff #(
        .WIDTH(PTR_WIDTH),
        .RESET_VALUE({PTR_WIDTH{1'b0}}),
        .ASYNC_RESET(1'b1),
        .HAS_ENABLE(1'b1)
    ) u_r_gray (
        .i_clk(i_r_clk),
        .i_rstb(i_r_rstb),
        .i_enable(o_r_init_done),
        .i_d(r_gray_next),
        .o_q(r_gray)
    );

    localparam bit VARIABLE_CAPTURE = 0;

    // Generic local-state primitives do not replace the attributed CDC chains.
    for (genvar stage = 0; stage < STAGES; stage++) begin : g_synchronizers
        if (stage == 0 && VARIABLE_CAPTURE) begin : g_capture_model
        end else begin : g_exact_capture
            always_ff @(posedge i_w_clk or negedge i_w_rstb) begin
                if (!i_w_rstb) begin
                    r_gray_sync[stage] <= '0;
                    r_up_sync[stage]   <= 1'b0;
                end else if (stage == 0) begin
                    r_gray_sync[stage] <= r_gray;
                    r_up_sync[stage]   <= r_up;
                end else begin
                    r_gray_sync[stage] <= r_gray_sync[stage-1];
                    r_up_sync[stage]   <= r_up_sync[stage-1];
                end
            end
            always_ff @(posedge i_r_clk or negedge i_r_rstb) begin
                if (!i_r_rstb) begin
                    w_gray_sync[stage] <= '0;
                    w_up_sync[stage]   <= 1'b0;
                end else if (stage == 0) begin
                    w_gray_sync[stage] <= w_gray;
                    w_up_sync[stage]   <= w_up;
                end else begin
                    w_gray_sync[stage] <= w_gray_sync[stage-1];
                    w_up_sync[stage]   <= w_up_sync[stage-1];
                end
            end
        end
    end

    // Once an observed peer drops out, advertise down until a local reset.
    // A returning peer alone must not reactivate stale pointer state.
    always_comb begin
        w_up_next = w_up;
        w_seen_remote_next = w_seen_remote;
        if (!w_seen_remote) w_up_next = 1'b1;
        if (r_up_sync[STAGES-1]) w_seen_remote_next = 1'b1;
        if (w_seen_remote && !r_up_sync[STAGES-1]) w_up_next = 1'b0;
    end
    always_comb begin
        r_up_next = r_up;
        r_seen_remote_next = r_seen_remote;
        if (!r_seen_remote) r_up_next = 1'b1;
        if (w_up_sync[STAGES-1]) r_seen_remote_next = 1'b1;
        if (r_seen_remote && !w_up_sync[STAGES-1]) r_up_next = 1'b0;
    end

    dff #(
        .WIDTH(2),
        .RESET_VALUE(2'b00),
        .ASYNC_RESET(1'b1),
        .HAS_ENABLE(1'b1)
    ) u_w_domain_state (
        .i_clk(i_w_clk),
        .i_rstb(i_w_rstb),
        .i_enable(1'b1),
        .i_d({w_up_next, w_seen_remote_next}),
        .o_q({w_up, w_seen_remote})
    );

    dff #(
        .WIDTH(2),
        .RESET_VALUE(2'b00),
        .ASYNC_RESET(1'b1),
        .HAS_ENABLE(1'b1)
    ) u_r_domain_state (
        .i_clk(i_r_clk),
        .i_rstb(i_r_rstb),
        .i_enable(1'b1),
        .i_d({r_up_next, r_seen_remote_next}),
        .o_q({r_up, r_seen_remote})
    );

    always_comb begin
        w_full_next  = 1'b1;
        w_level_next = '0;
        r_level_next = '0;
        if (o_w_init_done) begin
            w_full_next  = w_gray_next == (r_gray_sync[STAGES-1] ^ FULL_MASK);
            w_level_next = LEVEL_WIDTH'(w_bin_next - gray_to_binary(r_gray_sync[STAGES-1]));
        end
        if (o_r_init_done) begin
            r_level_next = LEVEL_WIDTH'(gray_to_binary(w_gray_sync[STAGES-1]) - r_bin_next);
        end
    end

    dff #(
        .WIDTH(LEVEL_WIDTH + 1),
        .RESET_VALUE({1'b1, {LEVEL_WIDTH{1'b0}}}),
        .ASYNC_RESET(1'b1),
        .HAS_ENABLE(1'b1)
    ) u_w_status (
        .i_clk(i_w_clk),
        .i_rstb(i_w_rstb),
        .i_enable(1'b1),
        .i_d({w_full_next, w_level_next}),
        .o_q({o_w_full, o_w_level})
    );

    dff #(
        .WIDTH(LEVEL_WIDTH + 1),
        .RESET_VALUE({1'b1, {LEVEL_WIDTH{1'b0}}}),
        .ASYNC_RESET(1'b1),
        .HAS_ENABLE(1'b1)
    ) u_r_status (
        .i_clk(i_r_clk),
        .i_rstb(i_r_rstb),
        .i_enable(1'b1),
        .i_d({!o_r_init_done || r_empty_next, r_level_next}),
        .o_q({o_r_empty, o_r_level})
    );

    // Neither storage contents nor storage port logic has a reset.
    always_ff @(posedge i_w_clk) begin
        if (push) memory[w_bin[ADDR_WIDTH-1:0]] <= i_w_data;
    end

    // Load the first visible head, or prefetch its successor on pop.
    // Stalled and invalid output data never follows the raw memory bus.
    assign r_data_enable = o_r_init_done && !r_empty_next && (o_r_empty || pop);
    assign r_data_next   = memory[r_bin_next[ADDR_WIDTH-1:0]];

    dff #(
        .WIDTH(REGISTER_WIDTH),
        .RESET_VALUE({REGISTER_WIDTH{1'b0}}),
        .ASYNC_RESET(1'b1),
        .HAS_ENABLE(1'b1)
    ) u_r_data (
        .i_clk(i_r_clk),
        .i_rstb(i_r_rstb),
        .i_enable(r_data_enable),
        .i_d(r_data_next),
        .o_q(o_r_data)
    );
endmodule
