# Asynchronous CAN RX is synchronized internally; cut only the external arrival.
# The two-flop CTU chain remains timed between its stages.
set_property ASYNC_REG TRUE [get_cells {VCU_INIT_i/ctu_can2/U0/can_inst/bus_sampling_inst/can_rx_sig_sync_inst/rff_reg VCU_INIT_i/ctu_can2/U0/can_inst/bus_sampling_inst/can_rx_sig_sync_inst/sync_reg}]
set_false_path -from [get_ports can2_rx] -to [get_pins VCU_INIT_i/ctu_can2/U0/can_inst/bus_sampling_inst/can_rx_sig_sync_inst/rff_reg/D]
# CAN TX has no external sampling clock; baud timing is handled by the protocol.
# Physical transceiver/propagation delays still require board validation.
set_false_path -to [get_ports {can0_tx can1_tx can2_tx}]
# PS CAN RX enters PS8 directly; PS-internal synchronizers have no PL timing endpoints.
