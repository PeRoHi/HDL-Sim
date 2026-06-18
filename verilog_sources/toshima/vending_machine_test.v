`timescale 1ps/1ps

module tb_vending_machine;



// �e�X�g���W���[���ւ̓��͐M��
reg clk;
reg sysreset;
reg insert_valid;
reg [15:0] insert_money;
reg [2:0] select;


// �e�X�g���W���[������̏o�͐M��
wire led_cola, led_greenTea, led_water, led_coffee;
wire [15:0] change;
wire [15:0] current_money;
wire out_cola, out_greenTea, out_water, out_coffee;


// �p�����[�^
parameter STEP = 50;

vending_machine vending_machine(
  clk,
  sysreset,
  insert_valid,
  insert_money,
  // �e�W���[�X�̃��C�g
  led_cola,
  led_greenTea,
  led_water,
  led_coffee,
  // �e�W���[�X�̔r�o�M��
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
  // ������
  clk = 0;
  sysreset = 0;
  insert_valid = 0;
  insert_money = 16'd0;
  select = 3'b000;


  #(STEP*2);
  sysreset = 1;

  

  #STEP;
  // 100�~���� 
  insert_money = 16'd100;
  insert_valid = 1;
  #STEP;
  insert_valid = 0;
  #STEP;

  // �����100�~���� (���v200�~)
  insert_money = 16'd100;
  insert_valid = 1;
  #STEP;
  insert_valid = 0;
  #STEP;

  // ��(150)���w��
  select = 3'b011;
  #STEP;

  select = 3'b000;
  #STEP;

  $finish;
end
endmodule