"""Wire sequencer, driver, passive monitor, scoreboard and coverage."""
from mosaic_uvm.components import VerificationEnv
from runtime_controller.agent import RuntimeAgent
from runtime_controller.scoreboard import RuntimeScoreboard
from runtime_controller.coverage import RuntimeCoverage


class RuntimeEnv(VerificationEnv):
    agent_type = RuntimeAgent
    scoreboard_type = RuntimeScoreboard
    coverage_type = RuntimeCoverage
