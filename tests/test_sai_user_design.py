"""Regression: user sai.v / saitest.v style Verilog."""

from hdl_sim.parser import parse_design

SAI_V = """
module sai (ck, reset, enable,lamp);
input ck,reset,enable;
output [6:0] lamp;
reg [2:0] cnt;
always @(posedge ck or posedge reset) begin
 if (reset == 1)
   cnt <= 1;
   else if (enable == 1)
      if (cnt == 6)
          cnt <= 1;
     else
          cnt <= cnt+1;
end
function [6:0] dec;
input [2:0] in;
  case (in)
    1 : dec = 7'b0001000;
    2 : dec = 7'b1000001;
    3 : dec = 7'b0011100;
    4 : dec = 7'b1010101;
    5 : dec = 7'b1011101;
    6 : dec = 7'b1110111;
    default : dec = 7'b0000000;
  endcase
endfunction
assign lamp = dec(cnt);
endmodule
"""

SAITEST_V = """
module sai_test;
reg ck, reset, enable;
wire [6:0] lamp;
parameter STEP = 1000;
sai sai( ck, reset, enable, lamp );
initial ck=0;
always#(STEP/2)
   ck = ~ck;
initial begin
		reset = 0; enable = 0;
   #STEP 	reset = 1;
   #STEP 	reset = 0;
   #STEP	enable = 1;
   #(STEP*5) 	enable = 0;
   #STEP 	enable = 1;
   #(STEP*5) $finish;
end
initial $monitor( $stime, " reset= %b enable= %b saikoro= %h lamp=%b", reset, enable, sai.cnt, lamp);
endmodule
"""


def test_parse_sai_and_testbench() -> None:
    design = parse_design(SAI_V + SAITEST_V)
    names = {m.name for m in design.modules}
    assert "sai" in names
    assert "sai_test" in names
    sai = design.module_by_name("sai")
    assert len(sai.ports) == 4
    assert len(sai.always_blocks) == 1
    sens = sai.always_blocks[0].sensitivity
    assert sens is not None
    assert len(sens) == 2
