`timescale 1ns/1ns
module tb_math_utils;
    reg [3:0] a;
    wire [15:0] fact_out;
    wire [2:0] pop_out;

    math_utils dut (.a(a), .fact_out(fact_out), .pop_out(pop_out));

    initial begin
        a = 4'd0; #10; // fact=1, pop=0
        a = 4'd3; #10; // fact=6, pop=2 (0011)
        a = 4'd5; #10; // fact=120, pop=2 (0101)
        a = 4'd7; #10; // fact=5040, pop=3 (0111)
        a = 4'd15; #10; // pop=4
        $finish;
    end
endmodule
