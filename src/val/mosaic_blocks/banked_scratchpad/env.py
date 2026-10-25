"""Connect a passive independent scoreboard and checked functional coverage."""
from mosaic_uvm.components import VerificationEnv
from banked_scratchpad.agent import ScratchpadAgent
from banked_scratchpad.coverage import ScratchpadCoverage
from banked_scratchpad.scoreboard import ScratchpadScoreboard


class ScratchpadEnv(VerificationEnv):
    agent_type = ScratchpadAgent
    scoreboard_type = ScratchpadScoreboard
    coverage_type = ScratchpadCoverage
