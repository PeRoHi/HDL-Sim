// Simple clock generator
module clock_tb;
  reg clk;

  initial begin
    clk = 0;
    forever begin
      #5 clk = ~clk;
    end
  end
endmodule
