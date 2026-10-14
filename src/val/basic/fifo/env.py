"""Connect the real-signal monitor, reference scoreboard and coverage."""

from mosaic_uvm.components import VerificationEnv
from fifo.agent import FifoAgent
from fifo.coverage import FifoCoverage
from fifo.scoreboard import FifoScoreboard


class FifoEnv(VerificationEnv):
    agent_type = FifoAgent
    scoreboard_type = FifoScoreboard
    coverage_type = FifoCoverage
