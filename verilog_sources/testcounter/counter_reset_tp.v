// リセット付き4ビットカウンタのテストモジュール

`timescale 1ps/1ps	// 単位時間を1psに設定

module counter_reset_tp;
reg				clk, reset;	// テスト入力をreg宣言
wire	[3:0]	out;		// 出力をwire宣言

parameter STEP = 1000;	// STEP = 1nsec に設定

counter_reset counter_reset( clk, reset, out );	// テスト対象呼び出し

always # (STEP/2)	clk = ~clk;		// クロック作成

// テスト入力
initial begin
				clk = 0;	reset = 0;	// 時間 = 0  nsec
	# (STEP)	reset = 1;				// 時間 = 1  nsec
	# (STEP)	reset = 0;				// 時間 = 2  nsec
	# (STEP*20)	reset = 1;				// 時間 = 22 nsec
	# (STEP)	reset = 0;				// 時間 = 23 nsec
	# (STEP*10)	$finish;				// 時間 = 33 nsec

end

// 表示
initial $monitor( $stime, " clk=%b reset=%b out=%h", clk, reset, out );

endmodule
