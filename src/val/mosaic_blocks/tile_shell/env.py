"""Connect independent scoreboards and checked coverage to the monitor."""
from mosaic_uvm.components import VerificationEnv
from tile_shell.agent import TileShellAgent
from tile_shell.coverage import TileShellCoverage
from tile_shell.scoreboard import TileShellScoreboard
class TileShellEnv(VerificationEnv):
    agent_type = TileShellAgent
    scoreboard_type = TileShellScoreboard
    coverage_type = TileShellCoverage
