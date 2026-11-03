// Observation only: no output feeds functional CAN/GPIO logic.
module can_io_observer(input wire clk, input wire can0_tx_raw,can0_rx_raw,can1_tx_raw,can1_rx_raw,can2_tx_raw,can2_rx_raw,
 input wire [7:0] gpio_i_raw, gpio_o_raw, gpio_t_raw,
 input wire gpio_resetn_raw, can2_resetn_raw,
 output wire [5:0] can_observed,
 output wire [7:0] gpio_i_observed, gpio_o_observed, gpio_t_observed,
 output wire [1:0] resetn_observed,
 output reg sample_tick = 0, output reg [31:0] timestamp = 0);
 (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) reg [31:0] obs_meta = 0, obs_sync = 0;
 reg [6:0] divider = 0;
 always @(posedge clk) begin
  obs_meta <= {can2_resetn_raw,gpio_resetn_raw,gpio_t_raw,gpio_o_raw,gpio_i_raw,can2_rx_raw,can2_tx_raw,can1_rx_raw,can1_tx_raw,can0_rx_raw,can0_tx_raw};
  obs_sync <= obs_meta;
  timestamp <= timestamp + 1'b1;
  sample_tick <= (divider == 99);
  divider <= (divider == 99) ? 0 : divider + 1'b1;
 end
 assign {resetn_observed,gpio_t_observed,gpio_o_observed,gpio_i_observed,can_observed} = obs_sync;
endmodule
