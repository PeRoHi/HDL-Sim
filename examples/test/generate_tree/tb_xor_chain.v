`timescale 1ns/1ns
module tb_xor_chain;
    reg [7:0] in;
    wire out;

    // パラメータを上書きしてインスタンス化
    xor_chain #(.WIDTH(8)) dut (
        .in(in),
        .out(out)
    );

    initial begin
        in = 8'b00000000; #10;
        in = 8'b00000001; #10;
        in = 8'b00000011; #10;
        in = 8'b10101010; #10; // 4 ones -> parity 0
        in = 8'b11101010; #10; // 5 ones -> parity 1
        $finish;
    end
endmodule
