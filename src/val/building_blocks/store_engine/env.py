"""Connect observed interface traffic to the checker and coverage collector."""
from mosaic_uvm.components import VerificationEnv
from store_engine.agent import StoreEngineAgent
from store_engine.coverage import StoreEngineCoverage
from store_engine.scoreboard import StoreEngineScoreboard


class StoreEngineEnv(VerificationEnv):
    agent_type = StoreEngineAgent
    scoreboard_type = StoreEngineScoreboard
    coverage_type = StoreEngineCoverage
