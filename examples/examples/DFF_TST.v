`timescale 1ns/1ns       
module DFF_tp;
reg   CLK, D, RST;  //　テスト入力をreg宣言   
wire  Q, QB;       //　出力をwire宣言

parameter STEP = 50;   
DFF  DFF(Q, QB, D, CLK, RST);  //　テスト対象呼び出し

always #(STEP/2)	CLK = ~CLK;    //　クロック作成
initial begin
	              RST = 1;  D = 0; CLK = 0;
	#(STEP/4)     RST = 0;
	#(STEP*3/4)             D = 1;
	#(STEP/4)     RST = 1;
        #(2*STEP)               D = 0;
	#STEP                   D = 1;
	#(STEP/2)     RST = 0;
	#(STEP/2)     RST = 1;
	#(STEP/4)    $finish;
	
end
endmodule