module DFF(Q, QB, D, CLK, RST);
input D, CLK, RST;
output Q, QB;
reg Q;

always @(posedge CLK or negedge RST)

if(RST == 1)
	 Q <=D ;
	else
	 Q <= 0;
assign QB = ~Q;
endmodule
