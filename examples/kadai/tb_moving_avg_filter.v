`timescale 1ns/1ps
//
// tb_moving_avg_filter
//   正弦波 + 単発スパイクノイズを入力し、各出力を検証する。
//   - VCD を出力して GTKWave で波形確認できる
//   - 立ち上がり区間を除外して、定量チェック (LPF 減衰 / ノイズ抽出) を行う
//
module tb_moving_avg_filter;

  localparam integer DATA_WIDTH = 12;
  localparam integer TAP_NUM    = 4;
  localparam integer NUM_SAMPLE = 128;

  // 出力レイテンシ (data_in 基準): group delay(N/2) + pipeline(1)
  localparam integer MATCH_DELAY = TAP_NUM/2 + 1;

  reg                         clk;
  reg                         rst_n;
  reg  signed [DATA_WIDTH-1:0] data_in;
  wire signed [DATA_WIDTH-1:0] lpf_out_single;
  wire signed [DATA_WIDTH-1:0] delay_matched_out;
  wire signed [DATA_WIDTH-1:0] noise_out;
  wire signed [DATA_WIDTH-1:0] lpf_out_cascade;

  moving_avg_filter #(
    .DATA_WIDTH (DATA_WIDTH),
    .TAP_NUM    (TAP_NUM)
  ) dut (
    .clk               (clk),
    .rst_n             (rst_n),
    .data_in           (data_in),
    .lpf_out_single    (lpf_out_single),
    .delay_matched_out (delay_matched_out),
    .noise_out         (noise_out),
    .lpf_out_cascade   (lpf_out_cascade)
  );

  // 100MHz クロック
  initial clk = 1'b0;
  always #5 clk = ~clk;

  // 入力信号生成用
  real    pi;
  real    sine_r;
  integer sine_i;
  integer spike;
  integer n;
  integer spike_cycle;
  integer spike_amp;

  // 計測用
  integer abs_noise;
  integer abs_lpf;
  integer peak_noise_spike;   // スパイク付近の |noise_out| ピーク
  integer peak_lpf_spike;     // 同タイミングの |lpf_out_single|
  integer peak_noise_quiet;   // 静穏区間の |noise_out| ピーク (参考)
  integer min_noise_quiet;    // 静穏区間の |noise_out| 最小 (ベースライン比較用)

  // 平滑性 (隣接サンプル差の絶対値和) 比較用
  integer prev_single;
  integer prev_cascade;
  integer rough_single;
  integer rough_cascade;
  integer diff_s;
  integer diff_c;

  initial begin
    $dumpfile("wave.vcd");
    $dumpvars(0, tb_moving_avg_filter);
  end

  initial begin
    pi          = 3.14159265358979;
    spike_cycle = 64;     // スパイクを入れるサンプル位置
    spike_amp   = 600;    // スパイク振幅
    peak_noise_spike = 0;
    peak_lpf_spike   = 0;
    peak_noise_quiet = 0;
    min_noise_quiet  = 999999;
    rough_single  = 0;
    rough_cascade = 0;
    prev_single   = 0;
    prev_cascade  = 0;

    data_in = 0;
    rst_n   = 1'b0;
    @(negedge clk);
    @(negedge clk);
    rst_n = 1'b1;

    for (n = 0; n < NUM_SAMPLE; n = n + 1) begin
      // 低周波正弦波 (周期 32 サンプル, 振幅 400)
      sine_r = 400.0 * $sin(2.0 * pi * n / 32.0);
      sine_i = $rtoi(sine_r);

      // 単発スパイクノイズ
      if (n == spike_cycle) spike = spike_amp;
      else                  spike = 0;

      data_in = sine_i + spike;
      @(negedge clk);

      abs_noise = (noise_out < 0) ? -noise_out : noise_out;
      abs_lpf   = (lpf_out_single < 0) ? -lpf_out_single : lpf_out_single;

      // スパイク付近 (フィルタ遅延を見込んだ出力側の窓) の noise ピークを捕捉
      if (n >= spike_cycle + MATCH_DELAY &&
          n <= spike_cycle + TAP_NUM + MATCH_DELAY + MATCH_DELAY) begin
        if (abs_noise > peak_noise_spike) begin
          peak_noise_spike = abs_noise;
          peak_lpf_spike   = abs_lpf;
        end
      end

      // 静穏区間 (立ち上がり・フィルタ安定後、スパイクの影響前)
      if (n >= 16 + MATCH_DELAY && n < spike_cycle - TAP_NUM - MATCH_DELAY) begin
        if (abs_noise > peak_noise_quiet) peak_noise_quiet = abs_noise;
        if (abs_noise < min_noise_quiet)  min_noise_quiet  = abs_noise;
      end

      // 平滑性: スパイク通過後の区間で隣接差の絶対値和を積算
      //   三角フィルタ (cascade) の方が滑らか = 差分和が小さいはず
      if (n >= spike_cycle + 8) begin
        diff_s = lpf_out_single - prev_single;
        diff_c = lpf_out_cascade - prev_cascade;
        rough_single  = rough_single  + ((diff_s < 0) ? -diff_s : diff_s);
        rough_cascade = rough_cascade + ((diff_c < 0) ? -diff_c : diff_c);
      end
      prev_single  = lpf_out_single;
      prev_cascade = lpf_out_cascade;
    end

    // ---- 定量チェック ----
    $display("=====================================================");
    $display(" spike_amp                 = %0d", spike_amp);
    $display(" peak |noise_out| @ spike  = %0d", peak_noise_spike);
    $display(" peak |noise_out| @ quiet  = %0d (max in quiet)", peak_noise_quiet);
    $display(" min  |noise_out| @ quiet  = %0d (baseline)", min_noise_quiet);
    $display(" |lpf_out_single| @ spike  = %0d (spike attenuated by ~1/N)", peak_lpf_spike);
    $display("=====================================================");

    // ノイズ抽出: スパイク付近の noise ピークがスパイクの 50%% 以上
    if (peak_noise_spike >= spike_amp/2)
      $display("[PASS] noise_out captured the spike (>= 50%% of spike_amp).");
    else
      $display("[FAIL] noise_out did not capture the spike.");

    // ハイパス特性: スパイク付近の noise が静穏区間の最小ベースラインより十分大きい
    // (静穏区間の最大値は正弦波残留で大きくなり得るため min と比較する)
    if (peak_noise_spike > min_noise_quiet * 2)
      $display("[PASS] spike clearly stands out in noise_out vs quiet baseline.");
    else
      $display("[FAIL] spike does not stand out in noise_out.");

    // 平滑性: カスケード出力の方が滑らか (隣接差分和が小さい)
    $display("-----------------------------------------------------");
    $display(" roughness lpf_out_single  = %0d", rough_single);
    $display(" roughness lpf_out_cascade = %0d", rough_cascade);
    if (rough_cascade <= rough_single)
      $display("[PASS] lpf_out_cascade is smoother than lpf_out_single.");
    else
      $display("[FAIL] cascade output is not smoother.");

    $display("Simulation done. Open wave.vcd with GTKWave to inspect waveforms.");
    $finish;
  end

endmodule
