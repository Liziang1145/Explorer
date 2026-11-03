################################################################################

# This XDC is used only for OOC mode of synthesis, implementation
# This constraints file contains default clock frequencies to be used during
# out-of-context flows such as OOC Synthesis and Hierarchical Designs.
# This constraints file is not used in normal top-down synthesis (default flow
# of Vivado)
################################################################################
create_clock -name eth_refclk_25 -period 40 [get_ports eth_refclk_25]
create_clock -name eth2_rgmii_rxc -period 10 [get_ports eth2_rgmii_rxc]
create_clock -name eth3_rgmii_rxc -period 10 [get_ports eth3_rgmii_rxc]

################################################################################