"""Keep stimulus, observation, prediction and functional coverage separate."""
from mosaic_uvm.components import VerificationEnv
from agu.agent import AguAgent
from agu.scoreboard import AguScoreboard
from agu.coverage import AguCoverage


class AguEnv(VerificationEnv):
    agent_type = AguAgent
    scoreboard_type = AguScoreboard
    coverage_type = AguCoverage
