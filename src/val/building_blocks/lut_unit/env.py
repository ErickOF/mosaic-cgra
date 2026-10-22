"""Connect independently observed traffic to the scoreboard and coverage."""
from mosaic_uvm.components import VerificationEnv
from lut_unit.agent import LutUnitAgent
from lut_unit.coverage import LutUnitCoverage
from lut_unit.scoreboard import LutUnitScoreboard


class LutUnitEnv(VerificationEnv):
    agent_type = LutUnitAgent
    scoreboard_type = LutUnitScoreboard
    coverage_type = LutUnitCoverage
