# Physical connector is now J19. Legacy gpio_j18 logical names retained for driver/probe compatibility.
# Offsets 0..7 follow J19 schematic physical pins 1..8, not Pmod IO1..IO8.
set_property PACKAGE_PIN AE12 [get_ports {gpio_j18[0]}]
set_property PACKAGE_PIN AF11 [get_ports {gpio_j18[1]}]
set_property PACKAGE_PIN AF12 [get_ports {gpio_j18[2]}]
set_property PACKAGE_PIN AG11 [get_ports {gpio_j18[3]}]
set_property PACKAGE_PIN AG10 [get_ports {gpio_j18[4]}]
set_property PACKAGE_PIN AH12 [get_ports {gpio_j18[5]}]
set_property PACKAGE_PIN AH10 [get_ports {gpio_j18[6]}]
set_property PACKAGE_PIN AH11 [get_ports {gpio_j18[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {gpio_j18[*]}]
set_property DRIVE 8 [get_ports {gpio_j18[*]}]
set_property SLEW SLOW [get_ports {gpio_j18[*]}]
