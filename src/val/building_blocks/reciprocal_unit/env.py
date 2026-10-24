"""Connect the passive monitor to the independent scoreboard and coverage."""
from mosaic_uvm.components import VerificationEnv
from reciprocal_unit.agent import ReciprocalAgent
from reciprocal_unit.coverage import ReciprocalCoverage
from reciprocal_unit.scoreboard import ReciprocalScoreboard


class ReciprocalEnv(VerificationEnv):
    agent_type = ReciprocalAgent
    scoreboard_type = ReciprocalScoreboard
    coverage_type = ReciprocalCoverage
