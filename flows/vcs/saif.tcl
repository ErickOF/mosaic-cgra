# Retain UCLI after cocotb finishes the simulation so activity can be reported.
# Requires the -ucli2Proc runtime option supplied by the saif target.
# The sv monitoring policy also needs -lca on VCS releases with LCA-gated SV-SAIF.
config endofsim noexit
power -gate_level all mda sv
power $env(MOSAIC_SAIF_SCOPE)
power -enable
run
power -disable
power -report $env(MOSAIC_SAIF_FILE) $env(MOSAIC_SAIF_TIME_UNIT) $env(MOSAIC_SAIF_SCOPE)
quit
