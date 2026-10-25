"""Connect observed interface traffic to the checker and coverage collector."""
from mosaic_uvm.components import VerificationEnv
from stream_formatter.agent import StreamFormatterAgent
from stream_formatter.coverage import StreamFormatterCoverage
from stream_formatter.scoreboard import StreamFormatterScoreboard


class StreamFormatterEnv(VerificationEnv):
    agent_type = StreamFormatterAgent
    scoreboard_type = StreamFormatterScoreboard
    coverage_type = StreamFormatterCoverage
