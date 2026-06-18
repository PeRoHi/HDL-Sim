`timescale 1ns/1ns
module reflex_game_tp;
    reg CLK, RST, START_BTN, STOP_BTN;
    wire LED_TARGET, LED_FOUL;
    wire [6:0] SEG_OUT;

    // �݌v������H���Ăяo��
    reflex_game dut (CLK, RST, START_BTN, STOP_BTN, LED_TARGET, LED_FOUL, SEG_OUT);

    // �N���b�N�̍쐬 (�e�L�X�gP.63�Q��)
    always #5 CLK = ~CLK;

    initial begin
        CLK = 0; RST = 1; START_BTN = 0; STOP_BTN = 0;
        #20 RST = 0;
        #20 START_BTN = 1; // �����ŃX�^�[�g�{�^��������
        #10 START_BTN = 0;
        #500 STOP_BTN = 1; 
        #20 STOP_BTN = 0;
        #3000 $finish;
    end
endmodule