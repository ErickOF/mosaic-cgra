"""Normal UVM agent/environment structure with reused driver and passive monitor."""
from cluster.driver import ClusterDriver
from cluster.monitor import ClusterMonitor
from cluster.events_scoreboard import EventCoverage, EventScoreboard
from mosaic_uvm.components import ActiveAgent, VerificationEnv


class EventAgent(ActiveAgent):
    driver_type = ClusterDriver
    monitor_type = ClusterMonitor


class EventEnv(VerificationEnv):
    agent_type = EventAgent
    scoreboard_type = EventScoreboard
    coverage_type = EventCoverage
