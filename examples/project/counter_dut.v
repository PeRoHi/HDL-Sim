// DUT: parameterized up-counter (project file 1/2)
`timescale 1ns/1ps

module counter_dut #(
    parameter WIDTH = 4
) (
    input clk,
    input rst,
    output [WIDTH-1:0] q
);
    reg [WIDTH-1:0] q;

    always @(posedge clk) begin
        if (rst)
            q <= 0;
        else
            q <= q + 1;
    end
endmodule
