set root [file normalize [file join [file dirname [info script]] ..]]
create_project -in_memory -part xck26-sfvc784-2LV-c
add_files [glob [file join $root rtl *.v]]
add_files -fileset sim_1 [file join $root tests tb_shadow.sv]
set_property top tb_shadow [get_filesets sim_1]
set_property xsim.simulate.runtime 0ns [get_filesets sim_1]
launch_simulation -mode behavioral
run 20ms
close_sim
