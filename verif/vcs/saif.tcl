# Retain UCLI after cocotb finishes the simulation so activity can be reported.
config endofsim noexit
power -gate_level all mda sv
power $env(MOSAIC_SAIF_SCOPE)
power -enable
run
power -disable
power -report $env(MOSAIC_SAIF_FILE) $env(MOSAIC_SAIF_TIME_UNIT) $env(MOSAIC_SAIF_SCOPE)
quit
