"""Connect the FIFO agent, independent scoreboard, and checked coverage."""

from mosaic_uvm.components import VerificationEnv
from async_fifo.agent import AsyncFifoAgent
from async_fifo.coverage import AsyncFifoCoverage
from async_fifo.scoreboard import AsyncFifoScoreboard


class AsyncFifoEnv(VerificationEnv):
    agent_type = AsyncFifoAgent
    scoreboard_type = AsyncFifoScoreboard
    coverage_type = AsyncFifoCoverage
