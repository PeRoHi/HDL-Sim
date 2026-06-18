module seg7_decoder(DIN, SEG);
    input [3:0] DIN;
    output [6:0] SEG;
    reg [6:0] SEG;

    always @(DIN) begin
        case (DIN)
            4'h0: SEG = 7'b0111111;
            4'h1: SEG = 7'b0000110;
            4'h2: SEG = 7'b1011011;
            4'h3: SEG = 7'b1001111;
            4'h4: SEG = 7'b1100110;
            4'h5: SEG = 7'b1101101;
            4'h6: SEG = 7'b1111101;
            4'h7: SEG = 7'b0100111;
            4'h8: SEG = 7'b1111111;
            4'h9: SEG = 7'b1101111;
            default: SEG = 7'b0000000;
        endcase
    end
endmodule
