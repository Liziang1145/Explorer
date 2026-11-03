//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
//--------------------------------------------------------------------------------
//Tool Version: Vivado v.2026.1 (win64) Build 6511674 Tue Jun 16 11:02:23 MDT 2026
//Date        : Tue Oct 13 20:44:33 2026
//Host        : ZKP-TX6PRO running 64-bit major release  (build 9200)
//Command     : generate_target VCU_INIT_wrapper.bd
//Design      : VCU_INIT_wrapper
//Purpose     : IP block netlist
//--------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

module kr260_j18_top
   (can0_rx,
    can0_tx,
    can1_rx,
    can1_tx,
    can2_rx,
    can2_tx,
    eth2_mdio_mdc,
    eth2_mdio_mdio_io,
    eth2_resetn,
    eth2_rgmii_rd,
    eth2_rgmii_rx_ctl,
    eth2_rgmii_rxc,
    eth2_rgmii_td,
    eth2_rgmii_tx_ctl,
    eth2_rgmii_txc,
    eth3_mdio_mdc,
    eth3_mdio_mdio_io,
    eth3_resetn,
    eth3_rgmii_rd,
    eth3_rgmii_rx_ctl,
    eth3_rgmii_rxc,
    eth3_rgmii_td,
    eth3_rgmii_tx_ctl,
    eth3_rgmii_txc,
    eth_refclk_25,
    gpio_j18);
  input can0_rx;
  output can0_tx;
  input can1_rx;
  output can1_tx;
  input can2_rx;
  output can2_tx;
  output eth2_mdio_mdc;
  inout eth2_mdio_mdio_io;
  output [0:0]eth2_resetn;
  input [3:0]eth2_rgmii_rd;
  input eth2_rgmii_rx_ctl;
  input eth2_rgmii_rxc;
  output [3:0]eth2_rgmii_td;
  output eth2_rgmii_tx_ctl;
  output eth2_rgmii_txc;
  output eth3_mdio_mdc;
  inout eth3_mdio_mdio_io;
  output [0:0]eth3_resetn;
  input [3:0]eth3_rgmii_rd;
  input eth3_rgmii_rx_ctl;
  input eth3_rgmii_rxc;
  output [3:0]eth3_rgmii_td;
  output eth3_rgmii_tx_ctl;
  output eth3_rgmii_txc;
  input eth_refclk_25;
  inout [7:0]gpio_j18;

  wire can0_rx;
  wire can0_tx;
  wire can1_rx;
  wire can1_tx;
  wire can2_rx;
  wire can2_tx;
  wire eth2_mdio_mdc;
  wire eth2_mdio_mdio_i;
  wire eth2_mdio_mdio_io;
  wire eth2_mdio_mdio_o;
  wire eth2_mdio_mdio_t;
  wire [0:0]eth2_resetn;
  wire [3:0]eth2_rgmii_rd;
  wire eth2_rgmii_rx_ctl;
  wire eth2_rgmii_rxc;
  wire [3:0]eth2_rgmii_td;
  wire eth2_rgmii_tx_ctl;
  wire eth2_rgmii_txc;
  wire eth3_mdio_mdc;
  wire eth3_mdio_mdio_i;
  wire eth3_mdio_mdio_io;
  wire eth3_mdio_mdio_o;
  wire eth3_mdio_mdio_t;
  wire [0:0]eth3_resetn;
  wire [3:0]eth3_rgmii_rd;
  wire eth3_rgmii_rx_ctl;
  wire eth3_rgmii_rxc;
  wire [3:0]eth3_rgmii_td;
  wire eth3_rgmii_tx_ctl;
  wire eth3_rgmii_txc;
  wire eth_refclk_25;
  wire [0:0]gpio_j18_tri_i_0;
  wire [1:1]gpio_j18_tri_i_1;
  wire [2:2]gpio_j18_tri_i_2;
  wire [3:3]gpio_j18_tri_i_3;
  wire [4:4]gpio_j18_tri_i_4;
  wire [5:5]gpio_j18_tri_i_5;
  wire [6:6]gpio_j18_tri_i_6;
  wire [7:7]gpio_j18_tri_i_7;
  wire [0:0]gpio_j18_0;
  wire [1:1]gpio_j18_1;
  wire [2:2]gpio_j18_2;
  wire [3:3]gpio_j18_3;
  wire [4:4]gpio_j18_4;
  wire [5:5]gpio_j18_5;
  wire [6:6]gpio_j18_6;
  wire [7:7]gpio_j18_7;
  wire [0:0]gpio_j18_tri_o_0;
  wire [1:1]gpio_j18_tri_o_1;
  wire [2:2]gpio_j18_tri_o_2;
  wire [3:3]gpio_j18_tri_o_3;
  wire [4:4]gpio_j18_tri_o_4;
  wire [5:5]gpio_j18_tri_o_5;
  wire [6:6]gpio_j18_tri_o_6;
  wire [7:7]gpio_j18_tri_o_7;
  wire [0:0]gpio_j18_tri_t_0;
  wire [1:1]gpio_j18_tri_t_1;
  wire [2:2]gpio_j18_tri_t_2;
  wire [3:3]gpio_j18_tri_t_3;
  wire [4:4]gpio_j18_tri_t_4;
  wire [5:5]gpio_j18_tri_t_5;
  wire [6:6]gpio_j18_tri_t_6;
  wire [7:7]gpio_j18_tri_t_7;

  VCU_INIT VCU_INIT_i
       (.can0_rx(can0_rx),
        .can0_tx(can0_tx),
        .can1_rx(can1_rx),
        .can1_tx(can1_tx),
        .can2_rx(can2_rx),
        .can2_tx(can2_tx),
        .eth2_mdio_mdc(eth2_mdio_mdc),
        .eth2_mdio_mdio_i(eth2_mdio_mdio_i),
        .eth2_mdio_mdio_o(eth2_mdio_mdio_o),
        .eth2_mdio_mdio_t(eth2_mdio_mdio_t),
        .eth2_resetn(eth2_resetn),
        .eth2_rgmii_rd(eth2_rgmii_rd),
        .eth2_rgmii_rx_ctl(eth2_rgmii_rx_ctl),
        .eth2_rgmii_rxc(eth2_rgmii_rxc),
        .eth2_rgmii_td(eth2_rgmii_td),
        .eth2_rgmii_tx_ctl(eth2_rgmii_tx_ctl),
        .eth2_rgmii_txc(eth2_rgmii_txc),
        .eth3_mdio_mdc(eth3_mdio_mdc),
        .eth3_mdio_mdio_i(eth3_mdio_mdio_i),
        .eth3_mdio_mdio_o(eth3_mdio_mdio_o),
        .eth3_mdio_mdio_t(eth3_mdio_mdio_t),
        .eth3_resetn(eth3_resetn),
        .eth3_rgmii_rd(eth3_rgmii_rd),
        .eth3_rgmii_rx_ctl(eth3_rgmii_rx_ctl),
        .eth3_rgmii_rxc(eth3_rgmii_rxc),
        .eth3_rgmii_td(eth3_rgmii_td),
        .eth3_rgmii_tx_ctl(eth3_rgmii_tx_ctl),
        .eth3_rgmii_txc(eth3_rgmii_txc),
        .eth_refclk_25(eth_refclk_25),
        .gpio_j18_tri_i({gpio_j18_tri_i_7,gpio_j18_tri_i_6,gpio_j18_tri_i_5,gpio_j18_tri_i_4,gpio_j18_tri_i_3,gpio_j18_tri_i_2,gpio_j18_tri_i_1,gpio_j18_tri_i_0}),
        .gpio_j18_tri_o({gpio_j18_tri_o_7,gpio_j18_tri_o_6,gpio_j18_tri_o_5,gpio_j18_tri_o_4,gpio_j18_tri_o_3,gpio_j18_tri_o_2,gpio_j18_tri_o_1,gpio_j18_tri_o_0}),
        .gpio_j18_tri_t({gpio_j18_tri_t_7,gpio_j18_tri_t_6,gpio_j18_tri_t_5,gpio_j18_tri_t_4,gpio_j18_tri_t_3,gpio_j18_tri_t_2,gpio_j18_tri_t_1,gpio_j18_tri_t_0}));
  IOBUF eth2_mdio_mdio_iobuf
       (.I(eth2_mdio_mdio_o),
        .IO(eth2_mdio_mdio_io),
        .O(eth2_mdio_mdio_i),
        .T(eth2_mdio_mdio_t));
  IOBUF eth3_mdio_mdio_iobuf
       (.I(eth3_mdio_mdio_o),
        .IO(eth3_mdio_mdio_io),
        .O(eth3_mdio_mdio_i),
        .T(eth3_mdio_mdio_t));
  IOBUF gpio_j18buf_0
       (.I(gpio_j18_tri_o_0),
        .IO(gpio_j18[0]),
        .O(gpio_j18_tri_i_0),
        .T(gpio_j18_tri_t_0));
  IOBUF gpio_j18buf_1
       (.I(gpio_j18_tri_o_1),
        .IO(gpio_j18[1]),
        .O(gpio_j18_tri_i_1),
        .T(gpio_j18_tri_t_1));
  IOBUF gpio_j18buf_2
       (.I(gpio_j18_tri_o_2),
        .IO(gpio_j18[2]),
        .O(gpio_j18_tri_i_2),
        .T(gpio_j18_tri_t_2));
  IOBUF gpio_j18buf_3
       (.I(gpio_j18_tri_o_3),
        .IO(gpio_j18[3]),
        .O(gpio_j18_tri_i_3),
        .T(gpio_j18_tri_t_3));
  IOBUF gpio_j18buf_4
       (.I(gpio_j18_tri_o_4),
        .IO(gpio_j18[4]),
        .O(gpio_j18_tri_i_4),
        .T(gpio_j18_tri_t_4));
  IOBUF gpio_j18buf_5
       (.I(gpio_j18_tri_o_5),
        .IO(gpio_j18[5]),
        .O(gpio_j18_tri_i_5),
        .T(gpio_j18_tri_t_5));
  IOBUF gpio_j18buf_6
       (.I(gpio_j18_tri_o_6),
        .IO(gpio_j18[6]),
        .O(gpio_j18_tri_i_6),
        .T(gpio_j18_tri_t_6));
  IOBUF gpio_j18buf_7
       (.I(gpio_j18_tri_o_7),
        .IO(gpio_j18[7]),
        .O(gpio_j18_tri_i_7),
        .T(gpio_j18_tri_t_7));
endmodule
