module debug_alu (
    input wire [3:0] a,
    input wire [3:0] b,
    input wire [2:0] op,
    output reg [3:0] out,
    output reg zero
);
    always @(*) begin
        case (op)
            3'b000: out = a + b;
            3'b001: out = a - b;
            3'b010: out = a & b;
            3'b011: out = a | b;
            3'b100: out = a ^ b;
            3'b101: out = ~a;
            3'b110: out = (a == b) ? 4'b0001 : 4'b0000;
            default: out = 4'b0000;
        endcase
        zero = (out == 4'b0000);
    end
endmodule
