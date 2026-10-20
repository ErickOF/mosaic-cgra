"""Connect commands, independent storage checking, and mandatory coverage."""

from mosaic_uvm.components import VerificationEnv
from context_memory.agent import ContextMemoryAgent
from context_memory.coverage import ContextMemoryCoverage
from context_memory.scoreboard import ContextMemoryScoreboard


class ContextMemoryEnv(VerificationEnv):
    agent_type = ContextMemoryAgent
    scoreboard_type = ContextMemoryScoreboard
    coverage_type = ContextMemoryCoverage
