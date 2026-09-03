`timescale 1ns/1ps
//
// delay_line
//   入力データを DELAY_CYCLE クロック分だけ遅延させるシフトレジスタ。
//   - 完全非同期リセット (rst_n Low で即時 0 クリア)
//   - DELAY_CYCLE = 0 のときは入力をそのまま通す
//
module delay_line #(
  parameter integer DATA_WIDTH  = 12,
  parameter integer DELAY_CYCLE = 2
) (
  input  wire                         clk,
  input  wire                         rst_n,
  input  wire signed [DATA_WIDTH-1:0] data_in,
  output wire signed [DATA_WIDTH-1:0] data_out
);

  generate
    if (DELAY_CYCLE == 0) begin : g_passthrough
      assign data_out = data_in;
    end else begin : g_delay
      reg signed [DATA_WIDTH-1:0] sreg [0:DELAY_CYCLE-1];
      integer i;

      always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
          for (i = 0; i < DELAY_CYCLE; i = i + 1) begin
            sreg[i] <= {DATA_WIDTH{1'b0}};
          end
        end else begin
          for (i = DELAY_CYCLE-1; i > 0; i = i - 1) begin
            sreg[i] <= sreg[i-1];
          end
          sreg[0] <= data_in;
        end
      end

      assign data_out = sreg[DELAY_CYCLE-1];
    end
  endgenerate

endmodule
