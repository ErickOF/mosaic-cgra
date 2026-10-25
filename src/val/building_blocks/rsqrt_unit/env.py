"""Connect the passive monitor to the independent scoreboard and coverage."""
from mosaic_uvm.components import VerificationEnv
from rsqrt_unit.agent import RsqrtAgent
from rsqrt_unit.coverage import RsqrtCoverage
from rsqrt_unit.scoreboard import RsqrtScoreboard


class RsqrtEnv(VerificationEnv):
    agent_type = RsqrtAgent
    scoreboard_type = RsqrtScoreboard
    coverage_type = RsqrtCoverage
