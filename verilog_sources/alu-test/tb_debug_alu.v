`timescale 1ns/1ns
module tb_debug_alu;
    reg [3:0] a, b;
    reg [2:0] op;
    wire [3:0] out;
    wire zero;

    debug_alu dut (
        .a(a), .b(b), .op(op),
        .out(out), .zero(zero)
    );

    initial begin
        a = 4'b0011; b = 4'b0101;
        
        op = 3'b000; #10; // ADD: 3 + 5 = 8
        op = 3'b001; #10; // SUB: 3 - 5 = -2 (1110)
        op = 3'b010; #10; // AND: 0011 & 0101 = 0001
        op = 3'b011; #10; // OR:  0011 | 0101 = 0111
        op = 3'b100; #10; // XOR: 0011 ^ 0101 = 0110
        op = 3'b101; #10; // NOT: ~0011 = 1100
        op = 3'b110; #10; // EQ:  3 == 5 -> 0
        
        a = 4'b0111; b = 4'b0111;
        op = 3'b110; #10; // EQ: 7 == 7 -> 1
        op = 3'b001; #10; // SUB: 7 - 7 = 0 (zero flag should be 1)
        
        #10 $finish;
    end
endmodule
