"""Connect observed signals to independent queue checking and coverage."""

from mosaic_uvm.components import VerificationEnv
from stream_fork.agent import StreamForkAgent
from stream_fork.coverage import StreamForkCoverage
from stream_fork.scoreboard import StreamForkScoreboard


class StreamForkEnv(VerificationEnv):
    agent_type = StreamForkAgent
    scoreboard_type = StreamForkScoreboard
    coverage_type = StreamForkCoverage
