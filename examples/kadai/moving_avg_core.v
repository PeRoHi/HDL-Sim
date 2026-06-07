`timescale 1ns/1ps
//
// moving_avg_core
//   N (= TAP_NUM) 点の移動平均フィルタ。
//   - ランニングサム方式: acc <= acc + new - oldest
//   - 内部アキュムレータは DATA_WIDTH + $clog2(TAP_NUM) bit (signed)
//   - 除算は算術右シフト (>>>) で行い、下位ビットを切り捨てて DATA_WIDTH に戻す
//   - 完全非同期リセット (rst_n Low で即時 0 クリア)
//   - TAP_NUM は 2 のべき乗であること (シフト除算のため)
//
module moving_avg_core #(
  parameter integer DATA_WIDTH = 12,
  parameter integer TAP_NUM    = 4
) (
  input  wire                       clk,
  input  wire                       rst_n,
  input  wire signed [DATA_WIDTH-1:0] data_in,
  output wire signed [DATA_WIDTH-1:0] data_out
);

  localparam integer SHIFT     = $clog2(TAP_NUM);
  localparam integer ACC_WIDTH = DATA_WIDTH + SHIFT;

  // 直近 TAP_NUM サンプルを保持するシフトレジスタ
  reg signed [DATA_WIDTH-1:0] buffer [0:TAP_NUM-1];
  reg signed [ACC_WIDTH-1:0]  acc;

  integer i;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      acc <= {ACC_WIDTH{1'b0}};
      for (i = 0; i < TAP_NUM; i = i + 1) begin
        buffer[i] <= {DATA_WIDTH{1'b0}};
      end
    end else begin
      // ランニングサム更新: 新サンプルを加算し、最古サンプルを減算
      // Sign-extend 12-bit to 14-bit explicitly to avoid ANY Verilog signedness quirks
      acc <= $signed(acc) + 
             $signed({ {SHIFT{data_in[DATA_WIDTH-1]}}, data_in }) - 
             $signed({ {SHIFT{buffer[TAP_NUM-1][DATA_WIDTH-1]}}, buffer[TAP_NUM-1] });
      for (i = TAP_NUM-1; i > 0; i = i - 1) begin
        buffer[i] <= buffer[i-1];
      end
      buffer[0] <= data_in;
    end
  end

  // 算術右シフトで N (= 2^SHIFT) 除算。$signed で符号を明示する。
  assign data_out = ($signed(acc)) >>> SHIFT;

endmodule
