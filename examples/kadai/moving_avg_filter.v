`timescale 1ns/1ps
//
// moving_avg_filter (top)
//   遅延補償付き移動平均・ノイズ抽出およびカスケード拡張回路。
//
//   構成:
//     data_in ┬─[MA_Stage1]─► lpf_out_single ─[MA_Stage2]─► lpf_out_cascade
//             │                     │
//             └─[delay_line]──► delay_matched_out
//                                   │
//                       noise_out = delay_matched_out - lpf_out_single
//
//   パラメータ:
//     DATA_WIDTH : データビット幅 (signed)
//     TAP_NUM    : 平均サンプル数 (2 のべき乗)
//
//   遅延整合に関する注意 (設計メモ参照):
//     移動平均コアは群遅延 round((N-1)/2) に加えて、アキュムレータの
//     レジスタによる 1 クロックのパイプライン遅延を持つ。仕様書 §4.4 の
//     DELAY_CYCLE = round((N-1)/2) はこのパイプライン分を含まないため、
//     ノイズ抽出の位相を正しく合わせるには遅延線をパイプライン分 (+1)
//     だけ深くする必要がある。本実装では MATCH_DELAY で補償する。
//
module moving_avg_filter #(
  parameter integer DATA_WIDTH = 12,
  parameter integer TAP_NUM    = 4
) (
  input  wire                         clk,
  input  wire                         rst_n,
  input  wire signed [DATA_WIDTH-1:0] data_in,
  output wire signed [DATA_WIDTH-1:0] lpf_out_single,
  output wire signed [DATA_WIDTH-1:0] delay_matched_out,
  output wire signed [DATA_WIDTH-1:0] noise_out,
  output wire signed [DATA_WIDTH-1:0] lpf_out_cascade
);

  // 仕様書 §3: 群遅延 round((N-1)/2)。N が 2 のべき乗 (偶数) なら N/2 に一致。
  localparam integer DELAY_CYCLE = TAP_NUM / 2;
  // 移動平均コアのパイプライン遅延 (アキュムレータ 1 段)
  localparam integer MA_PIPELINE = 1;
  // ノイズ抽出のための実遅延整合量
  localparam integer MATCH_DELAY = DELAY_CYCLE + MA_PIPELINE;

  // 1段目移動平均
  moving_avg_core #(
    .DATA_WIDTH (DATA_WIDTH),
    .TAP_NUM    (TAP_NUM)
  ) u_ma_stage1 (
    .clk      (clk),
    .rst_n    (rst_n),
    .data_in  (data_in),
    .data_out (lpf_out_single)
  );

  // 遅延整合 (group delay + pipeline)
  delay_line #(
    .DATA_WIDTH  (DATA_WIDTH),
    .DELAY_CYCLE (MATCH_DELAY)
  ) u_delay (
    .clk      (clk),
    .rst_n    (rst_n),
    .data_in  (data_in),
    .data_out (delay_matched_out)
  );

  // ノイズ抽出 (減算): 飽和なし、W bit へ wrap/truncate
  assign noise_out = delay_matched_out - lpf_out_single;

  // 2段目移動平均 (カスケード → 三角フィルタ)
  moving_avg_core #(
    .DATA_WIDTH (DATA_WIDTH),
    .TAP_NUM    (TAP_NUM)
  ) u_ma_stage2 (
    .clk      (clk),
    .rst_n    (rst_n),
    .data_in  (lpf_out_single),
    .data_out (lpf_out_cascade)
  );

endmodule
