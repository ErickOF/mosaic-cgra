"""Connect observed signals to independent queue checking and coverage."""

from mosaic_uvm.components import VerificationEnv
from stream_join.agent import StreamJoinAgent
from stream_join.coverage import StreamJoinCoverage
from stream_join.scoreboard import StreamJoinScoreboard


class StreamJoinEnv(VerificationEnv):
    agent_type = StreamJoinAgent
    scoreboard_type = StreamJoinScoreboard
    coverage_type = StreamJoinCoverage
