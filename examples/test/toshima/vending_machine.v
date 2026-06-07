module vending_machine(
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
  // おつり
  change,
  // ドリンクの選択
  select,
  // 現在の投入金額
  current_money
);

  input clk, sysreset;
  output out_coffee, out_cola, out_greenTea, out_water;
  reg out_coffee, out_cola, out_greenTea, out_water;
  input [15:0] insert_money;
  output [15:0] current_money;
  reg [15:0] current_money;

  input insert_valid;
  output led_cola, led_greenTea, led_water, led_coffee;

  output [15:0] change;
  reg [15:0] change;

  input [2:0] select;  
  
  // cola 200, greenTea 180, water 150, coffee 180
  parameter price_cola = 200;
  parameter price_greenTea = 180;
  parameter price_water = 150;
  parameter price_coffee = 180;
  
  // 購入可能表示（投入金額が商品価格以上のとき）
  assign led_cola = (current_money >= price_cola && (select == 3'b000 || select == 3'b001)) ? 1'b1 : 1'b0;
  assign led_greenTea = (current_money >= price_greenTea && (select == 3'b000 || select == 3'b010)) ? 1'b1 : 1'b0;
  assign led_water = (current_money >= price_water && (select == 3'b000 || select == 3'b011)) ? 1'b1 : 1'b0;
  assign led_coffee = (current_money >= price_coffee && (select == 3'b000 || select == 3'b100)) ? 1'b1 : 1'b0;

  


  always @(posedge clk or negedge sysreset) begin
    if (!sysreset) begin
      // リセット時の初期化
      current_money <= 16'd0;
      out_cola <= 1'b0;
      out_greenTea <= 1'b0;
      out_water <= 1'b0;
      out_coffee <= 1'b0;
      change <= 16'd0;
    
    end else begin

      // デフォルトでは排出信号を0にしておく
      out_cola <= 1'b0;
      out_greenTea <= 1'b0;
      out_water <= 1'b0;
      out_coffee <= 1'b0;
    
      // お金の投入
      if (insert_valid) begin
        current_money <= current_money + insert_money;
      end
      
      // 商品の購入（購入可能で、かつボタンが選択された場合）
      // select = (未選択: 3'b000, cola: 3'b001, greenTea: 3'b010, water: 3'b011, coffee: 3'b100)
      if (led_cola && select == 3'b001) begin
        out_cola <= 1'b1;
        change <= current_money - price_cola;
        current_money <= 16'd0;
      end
      else if (led_greenTea && select == 3'b010) begin
        out_greenTea <= 1'b1;
        change <= current_money - price_greenTea;
        current_money <= 16'd0;
      end
      else if (led_water && select == 3'b011) begin
        out_water <= 1'b1;
        change <= current_money - price_water;
        current_money <= 16'd0;
      end
      else if (led_coffee && select == 3'b100) begin
        out_coffee <= 1'b1;
        change <= current_money - price_coffee;
        current_money <= 16'd0;
      end
    end
  end
endmodule