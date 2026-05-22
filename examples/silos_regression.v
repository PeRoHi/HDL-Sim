// Silos-style regression: hierarchical DUT + clock/reset/stimulus/checker
`timescale 1ns/1ps

module counter #(
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

module silos_regression_tb;
    parameter WIDTH = 4;
    reg clk;
    reg rst;
    wire [WIDTH-1:0] count;

    counter #(.WIDTH(WIDTH)) dut (
        .clk(clk),
        .rst(rst),
        .q(count)
    );

    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    initial begin
        rst = 1;
        #12 rst = 0;
    end

    initial begin
        #50 begin
            if (count >= 4)
                $display("SILOS_REGRESSION PASS count=%0d", count);
            else
                $display("SILOS_REGRESSION FAIL count=%0d", count);
            $finish;
        end
    end
endmodule
