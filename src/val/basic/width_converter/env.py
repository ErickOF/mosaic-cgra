"""Connect checked observations to the separate model and coverage collector."""

from mosaic_uvm.components import VerificationEnv
from width_converter.agent import WidthConverterAgent
from width_converter.coverage import WidthConverterCoverage
from width_converter.scoreboard import WidthConverterScoreboard


class WidthConverterEnv(VerificationEnv):
    agent_type = WidthConverterAgent
    scoreboard_type = WidthConverterScoreboard
    coverage_type = WidthConverterCoverage
