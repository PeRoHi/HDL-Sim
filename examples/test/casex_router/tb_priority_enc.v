`timescale 1ns/1ns
module tb_priority_enc;
    reg [3:0] req;
    wire [1:0] grant;
    wire valid;

    priority_enc dut (.req(req), .grant(grant), .valid(valid));

    initial begin
        req = 4'b0000; #10;
        req = 4'b0001; #10;
        req = 4'b0101; #10; // bit 2 should win
        req = 4'b1001; #10; // bit 3 should win
        req = 4'b0110; #10;
        req = 4'b1111; #10;
        $finish;
    end
endmodule
