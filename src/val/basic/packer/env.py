"""Connect real-signal observations to reference checking and separate coverage."""

from mosaic_uvm.components import VerificationEnv
from packer.agent import PackerAgent
from packer.coverage import PackerCoverage
from packer.scoreboard import PackerScoreboard


class PackerEnv(VerificationEnv):
    agent_type = PackerAgent
    scoreboard_type = PackerScoreboard
    coverage_type = PackerCoverage
