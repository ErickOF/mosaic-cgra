"""Connect observed interface traffic to the checker and coverage collector."""
from mosaic_uvm.components import VerificationEnv
from load_engine.agent import LoadEngineAgent
from load_engine.coverage import LoadEngineCoverage
from load_engine.scoreboard import LoadEngineScoreboard


class LoadEngineEnv(VerificationEnv):
    agent_type = LoadEngineAgent
    scoreboard_type = LoadEngineScoreboard
    coverage_type = LoadEngineCoverage
