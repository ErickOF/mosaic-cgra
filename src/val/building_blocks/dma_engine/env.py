"""Connect independent protocol observations to reference and coverage."""
from mosaic_uvm.components import VerificationEnv
from dma_engine.agent import DmaAgent
from dma_engine.scoreboard import DmaScoreboard
from dma_engine.coverage import DmaCoverage


class DmaEnv(VerificationEnv):
    agent_type=DmaAgent
    scoreboard_type=DmaScoreboard
    coverage_type=DmaCoverage
