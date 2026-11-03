// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2026 Advanced Micro Devices, Inc. All Rights Reserved.
// -------------------------------------------------------------------------------
// This file contains confidential and proprietary information
// of AMD and is protected under U.S. and international copyright
// and other intellectual property laws.
//
// DISCLAIMER
// This disclaimer is not a license and does not grant any
// rights to the materials distributed herewith. Except as
// otherwise provided in a valid license issued to you by
// AMD, and to the maximum extent permitted by applicable
// law: (1) THESE MATERIALS ARE MADE AVAILABLE "AS IS" AND
// WITH ALL FAULTS, AND AMD HEREBY DISCLAIMS ALL WARRANTIES
// AND CONDITIONS, EXPRESS, IMPLIED, OR STATUTORY, INCLUDING
// BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, NON-
// INFRINGEMENT, OR FITNESS FOR ANY PARTICULAR PURPOSE; and
// (2) AMD shall not be liable (whether in contract or tort,
// including negligence, or under any other theory of
// liability) for any loss or damage of any kind or nature
// related to, arising under or in connection with these
// materials, including for any direct, or any indirect,
// special, incidental, or consequential loss or damage
// (including loss of data, profits, goodwill, or any type of
// loss or damage suffered as a result of any action brought
// by a third party) even if such damage or loss was
// reasonably foreseeable or AMD had been advised of the
// possibility of the same.
//
// CRITICAL APPLICATIONS
// AMD products are not designed or intended to be fail-
// safe, or for use in any application requiring fail-safe
// performance, such as life-support or safety devices or
// systems, Class III medical devices, nuclear facilities,
// applications related to the deployment of airbags, or any
// other applications that could lead to death, personal
// injury, or severe property or environmental damage
// (individually and collectively, "Critical
// Applications"). Customer assumes the sole risk and
// liability of any use of AMD products in Critical
// Applications, subject only to applicable laws and
// regulations governing limitations on product liability.
//
// THIS COPYRIGHT NOTICE AND DISCLAIMER MUST BE RETAINED AS
// PART OF THIS FILE AT ALL TIMES.
//
// DO NOT MODIFY THIS FILE.

// MODULE VLNV: amd.com:blockdesign:VCU_INIT:1.0

`timescale 1ps / 1ps

`include "vivado_interfaces.svh"

module VCU_INIT_sv (
  (* X_INTERFACE_IGNORE = "true" *)
  input wire [3:0] eth2_rgmii_rd,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire eth2_rgmii_rxc,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire eth2_rgmii_rx_ctl,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire [3:0] eth2_rgmii_td,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire eth2_rgmii_txc,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire eth2_rgmii_tx_ctl,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire eth2_mdio_mdc,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire eth2_mdio_mdio_i,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire eth2_mdio_mdio_o,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire eth2_mdio_mdio_t,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire [3:0] eth3_rgmii_rd,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire eth3_rgmii_rxc,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire eth3_rgmii_rx_ctl,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire [3:0] eth3_rgmii_td,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire eth3_rgmii_txc,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire eth3_rgmii_tx_ctl,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire eth3_mdio_mdc,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire eth3_mdio_mdio_i,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire eth3_mdio_mdio_o,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire eth3_mdio_mdio_t,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire [0:0] eth2_resetn,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire [0:0] eth3_resetn,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire eth_refclk_25,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire can0_rx,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire can0_tx,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire can1_rx,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire can1_tx,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire can2_rx,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire can2_tx,
  (* X_INTERFACE_IGNORE = "true" *)
  input wire [7:0] gpio_j18_tri_i,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire [7:0] gpio_j18_tri_o,
  (* X_INTERFACE_IGNORE = "true" *)
  output wire [7:0] gpio_j18_tri_t
);

  VCU_INIT inst (
    .eth2_rgmii_rd(eth2_rgmii_rd),
    .eth2_rgmii_rxc(eth2_rgmii_rxc),
    .eth2_rgmii_rx_ctl(eth2_rgmii_rx_ctl),
    .eth2_rgmii_td(eth2_rgmii_td),
    .eth2_rgmii_txc(eth2_rgmii_txc),
    .eth2_rgmii_tx_ctl(eth2_rgmii_tx_ctl),
    .eth2_mdio_mdc(eth2_mdio_mdc),
    .eth2_mdio_mdio_i(eth2_mdio_mdio_i),
    .eth2_mdio_mdio_o(eth2_mdio_mdio_o),
    .eth2_mdio_mdio_t(eth2_mdio_mdio_t),
    .eth3_rgmii_rd(eth3_rgmii_rd),
    .eth3_rgmii_rxc(eth3_rgmii_rxc),
    .eth3_rgmii_rx_ctl(eth3_rgmii_rx_ctl),
    .eth3_rgmii_td(eth3_rgmii_td),
    .eth3_rgmii_txc(eth3_rgmii_txc),
    .eth3_rgmii_tx_ctl(eth3_rgmii_tx_ctl),
    .eth3_mdio_mdc(eth3_mdio_mdc),
    .eth3_mdio_mdio_i(eth3_mdio_mdio_i),
    .eth3_mdio_mdio_o(eth3_mdio_mdio_o),
    .eth3_mdio_mdio_t(eth3_mdio_mdio_t),
    .eth2_resetn(eth2_resetn),
    .eth3_resetn(eth3_resetn),
    .eth_refclk_25(eth_refclk_25),
    .can0_rx(can0_rx),
    .can0_tx(can0_tx),
    .can1_rx(can1_rx),
    .can1_tx(can1_tx),
    .can2_rx(can2_rx),
    .can2_tx(can2_tx),
    .gpio_j18_tri_i(gpio_j18_tri_i),
    .gpio_j18_tri_o(gpio_j18_tri_o),
    .gpio_j18_tri_t(gpio_j18_tri_t)
  );

endmodule
