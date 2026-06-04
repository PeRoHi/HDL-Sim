`timescale 1ps/1ps

module tb_vending_machine;



// テストモジュールへの入力信号
reg clk;
reg sysreset;
reg insert_valid;
reg [15:0] insert_money;
reg [2:0] select;


// テストモジュールからの出力信号
wire led_cola, led_greenTea, led_water, led_coffee;
wire [15:0] change;
wire [15:0] current_money;
wire out_cola, out_greenTea, out_water, out_coffee;


// パラメータ
parameter STEP = 50;

vending_machine vending_machine(
  clk,
  sysreset,
  insert_valid,
  insert_money,
  // 各ジュースのライト
  led_cola,
  led_greenTea,
  led_water,
  led_coffee,
  // 各ジュースの排出信号
  out_cola,
  out_greenTea,
  out_water,
  out_coffee,
  change,
  select,
  current_money
);


always #(STEP/2) clk = ~clk;
initial begin
  // 初期化
  clk = 0;
  sysreset = 0;
  insert_valid = 0;
  insert_money = 16'd0;
  select = 3'b000;


  #(STEP*2);
  sysreset = 1;

  

  #STEP;
  // 100円投入 
  insert_money = 16'd100;
  insert_valid = 1;
  #STEP;
  insert_valid = 0;
  #STEP;

  // さらに100円投入 (合計200円)
  insert_money = 16'd100;
  insert_valid = 1;
  #STEP;
  insert_valid = 0;
  #STEP;

  // 水(150)を購入
  select = 3'b011;
  #STEP;

  select = 3'b000;
  #STEP;

  $finish;
end
endmodule