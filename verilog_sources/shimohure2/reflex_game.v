module reflex_game(CLK, RST, START_BTN, STOP_BTN, LED_TARGET, LED_FOUL, SEG_OUT);
    input CLK;
    input RST;
    input START_BTN;
    input STOP_BTN;
    output LED_TARGET;
    output LED_FOUL;
    output [6:0] SEG_OUT;

    // �����z��
    wire [7:0] random_val;
    wire [15:0] timer_val;
    wire timer_en, timer_rst;

    // (1) LFSR�Ăяo��
    lfsr8 u_lfsr (CLK, RST, random_val);

    // (2) �^�C�}�[�Ăяo��
    timer16 u_timer (CLK, timer_rst, timer_en, timer_val);

    // (3) �f�R�[�_�Ăяo��
    seg7_decoder u_seg (timer_val[3:0], SEG_OUT);

    // (4) ���C���R���g���[���Ăяo��
    main_controller u_ctrl (CLK, RST, START_BTN, STOP_BTN, random_val, timer_val, LED_TARGET, LED_FOUL, timer_en, timer_rst);

endmodule
