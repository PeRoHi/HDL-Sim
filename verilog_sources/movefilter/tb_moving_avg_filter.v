`timescale 1ns/1ps
//
// tb_moving_avg_filter
//   正弦波 + 3 点の単発スパイクノイズを入力し、各出力を検証する。
//   - VCD を出力して GTKWave で波形確認できる
//   - 立ち上がり区間を除外して、定量チェック (LPF 減衰 / ノイズ抽出) を行う
//
module tb_moving_avg_filter;

  localparam integer DATA_WIDTH = 12;
  localparam integer TAP_NUM    = 4;
  localparam integer NUM_SAMPLE = 128;
  localparam integer NUM_SPIKE  = 3;

  // 出力レイテンシ (data_in 基準): group delay(N/2) + pipeline(1)
  localparam integer MATCH_DELAY = TAP_NUM/2 + 1;

  // 3 つのスパイク注入位置 (窓が重ならないよう間隔を確保)
  localparam integer SPIKE_CYCLE_0 = 34;
  localparam integer SPIKE_CYCLE_1 = 64;
  localparam integer SPIKE_CYCLE_2 = 92;

  // 最終スパイク通過後、平滑性計測を始めるまでの余裕
  localparam integer SPIKE_SETTLE  = TAP_NUM + MATCH_DELAY * 2 + 6;
  localparam integer SMOOTH_START  = SPIKE_CYCLE_2 + SPIKE_SETTLE;

  // スパイク出力側の観測窓 (data_in 基準 n)
  localparam integer SPIKE_WIN_LO  = MATCH_DELAY;
  localparam integer SPIKE_WIN_HI  = TAP_NUM + MATCH_DELAY + MATCH_DELAY;

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
  integer s;
  integer abs_amp;

  // スパイク定義 (位置・振幅)
  integer spike_cycle [0:NUM_SPIKE-1];
  integer spike_amp   [0:NUM_SPIKE-1];

  // 計測用 (スパイクごと + 全体最大)
  integer peak_noise_spike [0:NUM_SPIKE-1];
  integer peak_lpf_spike   [0:NUM_SPIKE-1];
  integer peak_noise_spike_max;
  integer peak_lpf_spike_max;
  integer spikes_detected;
  integer abs_noise;
  integer abs_lpf;
  integer peak_noise_quiet;
  integer min_noise_quiet;

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
    pi = 3.14159265358979;

    // スパイク 0: 中振幅 / スパイク 1: 大振幅 / スパイク 2: 負極性
    spike_cycle[0] = SPIKE_CYCLE_0;
    spike_amp[0]   = 500;
    spike_cycle[1] = SPIKE_CYCLE_1;
    spike_amp[1]   = 1500;
    spike_cycle[2] = SPIKE_CYCLE_2;
    spike_amp[2]   = -500;

    peak_noise_spike_max = 0;
    peak_lpf_spike_max   = 0;
    peak_noise_quiet = 0;
    min_noise_quiet  = 999999;
    rough_single  = 0;
    rough_cascade = 0;
    prev_single   = 0;
    prev_cascade  = 0;

    for (s = 0; s < NUM_SPIKE; s = s + 1) begin
      peak_noise_spike[s] = 0;
      peak_lpf_spike[s]   = 0;
    end

    data_in = 0;
    rst_n   = 1'b0;
    @(negedge clk);
    @(negedge clk);
    rst_n = 1'b1;

    for (n = 0; n < NUM_SAMPLE; n = n + 1) begin
      // 低周波正弦波 (周期 32 サンプル, 振幅 400)
      sine_r = 400.0 * $sin(2.0 * pi * n / 32.0);
      sine_i = $rtoi(sine_r);

      // 3 点の単発スパイク
      spike = 0;
      for (s = 0; s < NUM_SPIKE; s = s + 1) begin
        if (n == spike_cycle[s])
          spike = spike_amp[s];
      end

      data_in = sine_i + spike;
      @(negedge clk);

      abs_noise = noise_out;
      if (abs_noise < 0) abs_noise = -abs_noise;
      abs_lpf = lpf_out_single;
      if (abs_lpf < 0) abs_lpf = -abs_lpf;

      // 各スパイクの観測窓で noise / lpf ピークを捕捉
      for (s = 0; s < NUM_SPIKE; s = s + 1) begin
        if (n >= spike_cycle[s] + SPIKE_WIN_LO &&
            n <= spike_cycle[s] + SPIKE_WIN_HI) begin
          if (abs_noise > peak_noise_spike[s]) begin
            peak_noise_spike[s] = abs_noise;
            peak_lpf_spike[s]   = abs_lpf;
          end
        end
      end

      // 静穏区間 (立ち上がり・フィルタ安定後、最初のスパイクの影響前)
      if (n >= 16 + MATCH_DELAY &&
          n < spike_cycle[0] - TAP_NUM - MATCH_DELAY) begin
        if (abs_noise > peak_noise_quiet) peak_noise_quiet = abs_noise;
        if (abs_noise < min_noise_quiet)  min_noise_quiet  = abs_noise;
      end

      // 平滑性: 最終スパイク通過後の定常正弦区間
      if (n >= SMOOTH_START) begin
        diff_s = lpf_out_single - prev_single;
        diff_c = lpf_out_cascade - prev_cascade;
        if (diff_s < 0) rough_single = rough_single - diff_s;
        else            rough_single = rough_single + diff_s;
        if (diff_c < 0) rough_cascade = rough_cascade - diff_c;
        else            rough_cascade = rough_cascade + diff_c;
      end
      prev_single  = lpf_out_single;
      prev_cascade = lpf_out_cascade;
    end

    // スパイクごとの集計 (閾値は各振幅の 25%)
    spikes_detected = 0;
    for (s = 0; s < NUM_SPIKE; s = s + 1) begin
      if (peak_noise_spike[s] > peak_noise_spike_max)
        peak_noise_spike_max = peak_noise_spike[s];
      if (peak_lpf_spike[s] > peak_lpf_spike_max)
        peak_lpf_spike_max = peak_lpf_spike[s];
      abs_amp = spike_amp[s];
      if (abs_amp < 0) abs_amp = -abs_amp;
      if (peak_noise_spike[s] >= abs_amp/4)
        spikes_detected = spikes_detected + 1;
    end

    // ---- 定量チェック ----
    $display("=====================================================");
    for (s = 0; s < NUM_SPIKE; s = s + 1) begin
      if (spike_amp[s] < 0) begin
        abs_amp = -spike_amp[s];
        $display(" spike%0d: cycle=%0d amp=-%0d  peak_noise=%0d",
                 s, spike_cycle[s], abs_amp, peak_noise_spike[s]);
      end else begin
        $display(" spike%0d: cycle=%0d amp=%0d  peak_noise=%0d",
                 s, spike_cycle[s], spike_amp[s], peak_noise_spike[s]);
      end
    end
    $display(" peak |noise_out| (max)    = %0d", peak_noise_spike_max);
    $display(" peak |noise_out| @ quiet  = %0d (max in quiet)", peak_noise_quiet);
    $display(" min  |noise_out| @ quiet  = %0d (baseline)", min_noise_quiet);
    $display(" |lpf_out_single| @ spike  = %0d (max, ~1/N attn)", peak_lpf_spike_max);
    $display("=====================================================");

    // ノイズ抽出: 3 スパイクのうち 2 点以上で十分なピーク
    if (spikes_detected >= 2)
      $display("[PASS] noise_out captured spikes (%0d/%0d >= 25%% of each amp).",
               spikes_detected, NUM_SPIKE);
    else
      $display("[FAIL] noise_out did not capture enough spikes (%0d/%0d).",
               spikes_detected, NUM_SPIKE);

    // ハイパス特性: 最大スパイクが静穏区間ベースラインより十分大きい
    if (peak_noise_spike_max > min_noise_quiet * 2)
      $display("[PASS] spikes clearly stand out in noise_out vs quiet baseline.");
    else
      $display("[FAIL] spikes do not stand out in noise_out.");

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
