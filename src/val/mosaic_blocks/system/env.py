"""Active host/memory agent, independent passive checker and coverage collector."""
from mosaic_uvm.components import VerificationEnv
from mosaic_blocks.system.agent import SystemAgent
from mosaic_blocks.system.scoreboard import SystemScoreboard
from mosaic_blocks.system.coverage import SystemCoverage

class SystemEnv(VerificationEnv):
    agent_type = SystemAgent
    scoreboard_type = SystemScoreboard
    coverage_type = SystemCoverage
