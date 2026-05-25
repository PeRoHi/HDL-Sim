// Testbench for counter_dut (project file 2/2)
`timescale 1ns/1ps

module tb_counter;
    reg clk, rst;
    wire [3:0] count;

    counter_dut #(.WIDTH(4)) dut (
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
                $display("COUNTER_PROJECT PASS count=%0d", count);
            else
                $display("COUNTER_PROJECT FAIL count=%0d", count);
            $finish;
        end
    end
endmodule
