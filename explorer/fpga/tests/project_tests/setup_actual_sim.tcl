create_fileset -simset sim_can_actual
set_property SOURCE_SET {} [get_filesets sim_can_actual]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/bit_err_detector.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/bit_err_detector.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/bus_sampling.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/bus_sampling.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/data_edge_detector.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/data_edge_detector.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/sample_mux.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/sample_mux.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/ssp_generator.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/ssp_generator.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/trv_delay_meas.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/trv_delay_meas.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/tx_data_cache.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/bus_sampling/tx_data_cache.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/bit_destuffing.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/bit_destuffing.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/bit_stuffing.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/bit_stuffing.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/bus_traffic_counters.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/bus_traffic_counters.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/can_core.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/can_core.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/can_crc.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/can_crc.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/control_counter.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/control_counter.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/crc_calc.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/crc_calc.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/err_counters.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/err_counters.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/err_detector.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/err_detector.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/fault_confinement.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/fault_confinement.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/fault_confinement_fsm.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/fault_confinement_fsm.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/fault_confinement_rules.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/fault_confinement_rules.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/operation_control.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/operation_control.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/protocol_control.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/protocol_control.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/protocol_control_fsm.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/protocol_control_fsm.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/reintegration_counter.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/reintegration_counter.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/retransmitt_counter.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/retransmitt_counter.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/rx_shift_reg.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/rx_shift_reg.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/trigger_mux.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/trigger_mux.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/tx_shift_reg.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_core/tx_shift_reg.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_top_ahb.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_top_ahb.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_top_apb.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_top_apb.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_top_level.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/can_top_level.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/dff_arst.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/dff_arst.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/dff_arst_ce.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/dff_arst_ce.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/dlc_decoder.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/dlc_decoder.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/endian_swapper.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/endian_swapper.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/inf_ram_wrapper.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/inf_ram_wrapper.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/majority_decoder_3.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/majority_decoder_3.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/rst_sync.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/rst_sync.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/shift_reg.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/shift_reg.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/shift_reg_byte.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/shift_reg_byte.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/shift_reg_preload.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/shift_reg_preload.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/sig_sync.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/common/sig_sync.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/frame_filters/bit_filter.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/frame_filters/bit_filter.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/frame_filters/frame_filters.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/frame_filters/frame_filters.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/frame_filters/range_filter.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/frame_filters/range_filter.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/interface/ahb_ifc.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/interface/ahb_ifc.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/interface/apb_ifc.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/interface/apb_ifc.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/interrupts/int_manager.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/interrupts/int_manager.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/interrupts/int_module.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/interrupts/int_module.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_components.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_components.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_config.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_config.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_constants.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_constants.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_fd_frame_format.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_fd_frame_format.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_fd_register_map.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_fd_register_map.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_types.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/can_types.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/cmn_lib.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/cmn_lib.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/drv_stat_pkg.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/drv_stat_pkg.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/id_transfer.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/id_transfer.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/reduce_lib.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/lib/reduce_lib.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/access_signaler.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/access_signaler.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/address_decoder.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/address_decoder.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/can_registers_pkg.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/can_registers_pkg.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/cmn_reg_map_pkg.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/cmn_reg_map_pkg.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/control_registers_reg_map.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/control_registers_reg_map.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/data_mux.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/data_mux.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/memory_bus.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/memory_bus.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/memory_reg.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/generated/memory_reg.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/memory_registers.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/memory_registers/memory_registers.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/bit_segment_meter.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/bit_segment_meter.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/bit_time_cfg_capture.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/bit_time_cfg_capture.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/bit_time_counters.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/bit_time_counters.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/bit_time_fsm.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/bit_time_fsm.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/prescaler.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/prescaler.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/segment_end_detector.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/segment_end_detector.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/synchronisation_checker.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/synchronisation_checker.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/trigger_generator.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/prescaler/trigger_generator.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/rx_buffer/rx_buffer.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/rx_buffer/rx_buffer.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/rx_buffer/rx_buffer_fsm.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/rx_buffer/rx_buffer_fsm.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/rx_buffer/rx_buffer_pointers.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/rx_buffer/rx_buffer_pointers.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/rx_buffer/rx_buffer_ram.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/rx_buffer/rx_buffer_ram.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/tx_arbitrator/priority_decoder.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/tx_arbitrator/priority_decoder.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/tx_arbitrator/tx_arbitrator.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/tx_arbitrator/tx_arbitrator.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/tx_arbitrator/tx_arbitrator_fsm.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/tx_arbitrator/tx_arbitrator_fsm.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/txt_buffer/txt_buffer.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/txt_buffer/txt_buffer.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/txt_buffer/txt_buffer_fsm.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/txt_buffer/txt_buffer_fsm.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/txt_buffer/txt_buffer_ram.vhd}
set_property library ctu_can_fd_rtl [get_files {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/third_party/ctucanfd/src/txt_buffer/txt_buffer_ram.vhd}]
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/rtl/can_axil_endpoint.v}
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/rtl/can_path_owner.v}
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/rtl/can_core_service.v}
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/rtl/arm_command_engine.v}
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/rtl/can_path_control.v}
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/rtl/can_passive_monitor.v}
add_files -fileset sim_can_actual {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/tests/tb_can_actual.sv}
set_property top tb_can_actual [get_filesets sim_can_actual]
set_property xsim.simulate.runtime 0ns [get_filesets sim_can_actual]
current_fileset -simset [get_filesets sim_can_actual]
update_compile_order -fileset sim_can_actual
