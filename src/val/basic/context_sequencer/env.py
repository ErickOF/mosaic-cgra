"""Wire the active agent, independent scoreboard, and mandatory coverage."""

from mosaic_uvm.components import VerificationEnv
from context_sequencer.agent import SequencerAgent
from context_sequencer.coverage import SequencerCoverage
from context_sequencer.scoreboard import SequencerScoreboard


class SequencerEnv(VerificationEnv):
    agent_type = SequencerAgent
    coverage_type = SequencerCoverage
    scoreboard_type = SequencerScoreboard
