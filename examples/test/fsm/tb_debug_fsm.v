`timescale 1ns/1ns
module tb_debug_fsm;
    reg clk, rst_n, din;
    wire detected;

    debug_fsm dut (.clk(clk), .rst_n(rst_n), .din(din), .detected(detected));

    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    initial begin
        rst_n = 0; din = 0;
        #12 rst_n = 1;
        
        // Feed: 0 1 1 0 1 (Detect!) 1 0 1 (Detect!) 0
        #10 din = 0;
        #10 din = 1;
        #10 din = 1;
        #10 din = 0;
        #10 din = 1; // detected should go high after next clock
        #10 din = 1;
        #10 din = 0;
        #10 din = 1; // detected again
        #10 din = 0;
        
        #20 $finish;
    end
endmodule
