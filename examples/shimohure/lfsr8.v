module lfsr8(CLK, RST, RAND_OUT);
    input CLK;
    input RST;
    output [7:0] RAND_OUT;
    reg [7:0] RAND_OUT;

    always @(posedge CLK or posedge RST) begin
        if (RST) RAND_OUT <= 8'b10101010;
        else RAND_OUT <= {RAND_OUT[6:0], RAND_OUT[7] ^ RAND_OUT[5] ^ RAND_OUT[4] ^ RAND_OUT[3]};
    end
endmodule
