`timescale 1ns/1ns
module tb_debug_shift;
    reg clk, rst_n, shift_en, din;
    wire [3:0] q;

    debug_shift dut (
        .clk(clk), .rst_n(rst_n), .shift_en(shift_en),
        .din(din), .q(q)
    );

    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    initial begin
        rst_n = 0; shift_en = 0; din = 0;
        #12 rst_n = 1;
        
        // Shift in 1, 0, 1, 1
        #10 shift_en = 1; din = 1;
        #10 shift_en = 1; din = 0;
        #10 shift_en = 1; din = 1;
        #10 shift_en = 1; din = 1;
        #10 shift_en = 0; din = 0; // Hold value
        
        #20 $finish;
    end
endmodule
