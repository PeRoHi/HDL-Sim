// tb_reaction_timer.v
`timescale 1ns / 1ps

module tb_reaction_timer;

    reg clk;
    reg rst_n;
    reg btn_start;
    reg btn_stop;
    wire led;
    wire [6:0] seg0, seg1, seg2, seg3;

    reaction_timer_top uut (
        .clk(clk),
        .rst_n(rst_n),
        .btn_start(btn_start),
        .btn_stop(btn_stop),
        .led(led),
        .seg0(seg0), .seg1(seg1), .seg2(seg2), .seg3(seg3)
    );

    // クロック生成 (10MHz -> 100ns周期)
    initial begin
        clk = 0;
        forever #50 clk = ~clk;
    end

    initial begin
        // 初期化
        // $dumpfile("dump.vcd");              // ← コメントアウト
        // $dumpvars(0, tb_reaction_timer);    // ← コメントアウト
        
        rst_n = 0; btn_start = 0; btn_stop = 0;
        #200 rst_n = 1;

        // --- シナリオ1: 正常に計測 ---
        #100 btn_start = 1; #100 btn_start = 0;
        
        // LEDが点灯するまで待つ
        wait(led == 1);
        
        // 反応時間 (適当なディレイ)
        #15400; 
        
        btn_stop = 1; #100 btn_stop = 0;
        #500;

        // --- シナリオ2: フライング (LED点灯前に押す) ---
        #100 btn_start = 1; #100 btn_start = 0;
        
        #2000; // LEDが点灯する前に押す
        btn_stop = 1; #100 btn_stop = 0;
        
        #500;
        
        $finish;
    end

endmodule