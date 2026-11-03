//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
//--------------------------------------------------------------------------------
//Tool Version: Vivado v.2026.1 (win64) Build 6511674 Tue Jun 16 11:02:23 MDT 2026
//Date        : Tue Nov  3 19:13:56 2026
//Host        : ZKP-TX6PRO running 64-bit major release  (build 9200)
//Command     : generate_target VCU_INIT_wrapper.bd
//Design      : VCU_INIT_wrapper
//Purpose     : IP block netlist
//--------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

module VCU_INIT_wrapper
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
    gpio_j18_tri_i,
    gpio_j18_tri_o,
    gpio_j18_tri_t);
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
  input [7:0]gpio_j18_tri_i;
  output [7:0]gpio_j18_tri_o;
  output [7:0]gpio_j18_tri_t;

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
  wire [7:0]gpio_j18_tri_i;
  wire [7:0]gpio_j18_tri_o;
  wire [7:0]gpio_j18_tri_t;

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
        .gpio_j18_tri_i(gpio_j18_tri_i),
        .gpio_j18_tri_o(gpio_j18_tri_o),
        .gpio_j18_tri_t(gpio_j18_tri_t));
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
endmodule
