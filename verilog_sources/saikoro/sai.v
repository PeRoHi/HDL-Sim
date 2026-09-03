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