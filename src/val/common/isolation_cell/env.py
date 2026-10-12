"""IsolationCell env components for specification-based PyUVM validation."""

from isolation_cell.agent import IsolationCellAgent
from isolation_cell.coverage import IsolationCellCoverage
from isolation_cell.scoreboard import IsolationCellScoreboard
from mosaic_uvm.components import VerificationEnv


class IsolationCellEnv(VerificationEnv):
    agent_type = IsolationCellAgent
    scoreboard_type = IsolationCellScoreboard
    coverage_type = IsolationCellCoverage
