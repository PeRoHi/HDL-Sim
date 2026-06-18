module timer16(CLK, RST, EN, COUNT);
    input CLK;
    input RST;
    input EN;
    output [15:0] COUNT;
    reg [15:0] COUNT;

    always @(posedge CLK) begin
        if (RST) COUNT <= 16'd0;
        else if (EN) COUNT <= COUNT + 16'd1;
    end
endmodule
