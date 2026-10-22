"""Connect observed interface traffic to the checker and coverage collector."""
from mosaic_uvm.components import VerificationEnv
from event_barrier.agent import EventBarrierAgent
from event_barrier.coverage import EventBarrierCoverage
from event_barrier.scoreboard import EventBarrierScoreboard


class EventBarrierEnv(VerificationEnv):
    agent_type = EventBarrierAgent
    scoreboard_type = EventBarrierScoreboard
    coverage_type = EventBarrierCoverage
