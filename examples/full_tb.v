// Integration example: counter + case + display + finish
module full_tb;
  reg clk;
  reg [3:0] count;

  initial begin
    clk = 0;
    forever #5 clk = ~clk;
  end

  always @(posedge clk) begin
    count <= count + 1;
  end

  initial begin
    #40 begin
      case (count)
        4'd4: $display("count reached %d", count);
        default: $display("count=%d", count);
      endcase
      $finish;
    end
  end
endmodule
