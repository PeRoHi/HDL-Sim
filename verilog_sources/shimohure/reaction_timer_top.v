// reaction_timer_top.v
module reaction_timer_top (
    input wire clk,
    input wire rst_n,
    input wire btn_start,
    input wire btn_stop,
    output wire led,
    output wire [6:0] seg0,
    output wire [6:0] seg1,
    output wire [6:0] seg2,
    output wire [6:0] seg3
);

    wire [7:0] random_val;
    wire [15:0] count_val;
    wire timer_en;
    wire timer_rst;
    wire [3:0] bcd0, bcd1, bcd2, bcd3;

    // モジュールのインスタンス化
    lfsr_8bit u_lfsr (
        .clk(clk),
        .rst_n(rst_n),
        .rand_out(random_val)
    );

    main_controller u_ctrl (
        .clk(clk),
        .rst_n(rst_n),
        .btn_start(btn_start),
        .btn_stop(btn_stop),
        .random_val(random_val),
        .led(led),
        .timer_en(timer_en),
        .timer_rst(timer_rst)
    );

    timer_bcd u_timer (
        .clk(clk),
        .rst_n(rst_n),
        .en(timer_en),
        .clr(timer_rst),
        .bcd0(bcd0),
        .bcd1(bcd1),
        .bcd2(bcd2),
        .bcd3(bcd3)
    );

    seg7_decoder u_seg0 (.bcd(bcd0), .seg(seg0));
    seg7_decoder u_seg1 (.bcd(bcd1), .seg(seg1));
    seg7_decoder u_seg2 (.bcd(bcd2), .seg(seg2));
    seg7_decoder u_seg3 (.bcd(bcd3), .seg(seg3));

endmodule