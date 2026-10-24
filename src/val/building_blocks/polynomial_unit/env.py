"""Connect the passive monitor to the independent scoreboard and coverage."""
from mosaic_uvm.components import VerificationEnv
from polynomial_unit.agent import PolynomialAgent
from polynomial_unit.coverage import PolynomialCoverage
from polynomial_unit.scoreboard import PolynomialScoreboard


class PolynomialEnv(VerificationEnv):
    agent_type = PolynomialAgent
    scoreboard_type = PolynomialScoreboard
    coverage_type = PolynomialCoverage
